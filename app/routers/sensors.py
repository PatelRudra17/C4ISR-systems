from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from influxdb_client import Point
from influxdb_client.client.influxdb_client_async import InfluxDBClientAsync

from app.core.config import get_settings
from app.core.redis_client import publish_event
from app.models.models import User
from app.routers.auth import get_current_user, require_permission

settings = get_settings()
router = APIRouter(prefix="/api/v1/sensors", tags=["Sensors"])


class SensorReading(BaseModel):
    sensor_id: str
    sensor_type: str  # RADAR, CAMERA, THERMAL, ACOUSTIC, etc.
    value: float
    lat: Optional[float] = None
    lng: Optional[float] = None
    altitude_m: Optional[float] = None
    metadata: Optional[dict] = None


class RadarContact(BaseModel):
    sensor_id: str
    contact_id: str
    range_m: float
    bearing_deg: float
    speed_ms: float
    altitude_m: float
    classification: str  # UNKNOWN, FRIENDLY, HOSTILE, NEUTRAL
    rcs: Optional[float] = None  # Radar Cross Section
    lat: Optional[float] = None
    lng: Optional[float] = None


@router.post("/reading")
async def log_sensor_reading(
    reading: SensorReading,
    user: User = Depends(require_permission("sensors:rw"))
):
    """Log single sensor reading to InfluxDB"""
    async with InfluxDBClientAsync(
        url=settings.INFLUX_URL,
        token=settings.INFLUX_TOKEN,
        org=settings.INFLUX_ORG
    ) as client:
        write_api = client.write_api()

        point = Point("sensor_data") \
            .tag("sensor_id", reading.sensor_id) \
            .tag("sensor_type", reading.sensor_type) \
            .field("value", reading.value) \
            .time(datetime.utcnow())

        if reading.lat is not None:
            point = point.field("lat", reading.lat)
        if reading.lng is not None:
            point = point.field("lng", reading.lng)
        if reading.altitude_m is not None:
            point = point.field("altitude_m", reading.altitude_m)

        await write_api.write(bucket=settings.INFLUX_BUCKET_SENSOR, record=point)

    return {
        "message": "Sensor reading logged",
        "sensor_id": reading.sensor_id,
        "timestamp": datetime.utcnow().isoformat()
    }


@router.post("/reading/batch")
async def log_sensor_readings_batch(
    readings: List[SensorReading],
    user: User = Depends(require_permission("sensors:rw"))
):
    """Log multiple sensor readings (max 1000)"""
    if len(readings) > 1000:
        raise HTTPException(status_code=400, detail="Maximum 1000 readings per batch")

    async with InfluxDBClientAsync(
        url=settings.INFLUX_URL,
        token=settings.INFLUX_TOKEN,
        org=settings.INFLUX_ORG
    ) as client:
        write_api = client.write_api()

        points = []
        for reading in readings:
            point = Point("sensor_data") \
                .tag("sensor_id", reading.sensor_id) \
                .tag("sensor_type", reading.sensor_type) \
                .field("value", reading.value) \
                .time(datetime.utcnow())

            if reading.lat is not None:
                point = point.field("lat", reading.lat)
            if reading.lng is not None:
                point = point.field("lng", reading.lng)
            if reading.altitude_m is not None:
                point = point.field("altitude_m", reading.altitude_m)

            points.append(point)

        await write_api.write(bucket=settings.INFLUX_BUCKET_SENSOR, record=points)

    return {
        "message": f"{len(readings)} sensor readings logged",
        "timestamp": datetime.utcnow().isoformat()
    }


@router.post("/radar/contact")
async def log_radar_contact(
    contact: RadarContact,
    user: User = Depends(require_permission("sensors:rw"))
):
    """Log radar contact detection"""
    # Write to InfluxDB
    async with InfluxDBClientAsync(
        url=settings.INFLUX_URL,
        token=settings.INFLUX_TOKEN,
        org=settings.INFLUX_ORG
    ) as client:
        write_api = client.write_api()

        point = Point("radar_contacts") \
            .tag("sensor_id", contact.sensor_id) \
            .tag("contact_id", contact.contact_id) \
            .tag("classification", contact.classification) \
            .field("range_m", contact.range_m) \
            .field("bearing_deg", contact.bearing_deg) \
            .field("speed_ms", contact.speed_ms) \
            .field("altitude_m", contact.altitude_m) \
            .time(datetime.utcnow())

        if contact.rcs is not None:
            point = point.field("rcs", contact.rcs)
        if contact.lat is not None:
            point = point.field("lat", contact.lat)
        if contact.lng is not None:
            point = point.field("lng", contact.lng)

        await write_api.write(bucket=settings.INFLUX_BUCKET_SENSOR, record=point)

    # If hostile, publish to threats channel
    if contact.classification == "HOSTILE":
        await publish_event("threats.live", {
            "source": "RADAR",
            "sensor_id": contact.sensor_id,
            "contact_id": contact.contact_id,
            "lat": contact.lat,
            "lng": contact.lng,
            "range_m": contact.range_m,
            "bearing_deg": contact.bearing_deg,
            "speed_ms": contact.speed_ms,
            "detected_at": datetime.utcnow().isoformat()
        })

    return {
        "message": "Radar contact logged",
        "contact_id": contact.contact_id,
        "classification": contact.classification
    }


@router.get("/history/{sensor_id}")
async def get_sensor_history(
    sensor_id: str,
    hours: int = 24,
    user: User = Depends(require_permission("sensors:r"))
):
    """Get historical sensor data from InfluxDB"""
    async with InfluxDBClientAsync(
        url=settings.INFLUX_URL,
        token=settings.INFLUX_TOKEN,
        org=settings.INFLUX_ORG
    ) as client:
        query_api = client.query_api()

        flux_query = f'''
        from(bucket: "{settings.INFLUX_BUCKET_SENSOR}")
          |> range(start: -{hours}h)
          |> filter(fn: (r) => r["_measurement"] == "sensor_data")
          |> filter(fn: (r) => r["sensor_id"] == "{sensor_id}")
          |> sort(columns: ["_time"])
        '''

        tables = await query_api.query(flux_query)

        data_points = []
        for table in tables:
            for record in table.records:
                data_points.append({
                    "time": record["_time"].isoformat(),
                    "field": record["_field"],
                    "value": record["_value"],
                    "sensor_type": record.values.get("sensor_type", "UNKNOWN")
                })

        return {
            "sensor_id": sensor_id,
            "data_points": data_points,
            "count": len(data_points)
        }
