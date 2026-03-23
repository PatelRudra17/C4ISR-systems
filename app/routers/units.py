from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from pydantic import BaseModel
from typing import List, Dict
from datetime import datetime
from influxdb_client import Point
from influxdb_client.client.influxdb_client_async import InfluxDBClientAsync

from app.core.database import get_db
from app.core.redis_client import set_unit_position, get_all_unit_positions, subscribe_channel
from app.core.config import get_settings
from app.models.models import Unit, User
from app.routers.auth import get_current_user, require_permission

settings = get_settings()
router = APIRouter(prefix="/api/v1/units", tags=["Units"])


class PositionUpdate(BaseModel):
    lat: float
    lng: float
    altitude_m: float = 0.0
    heading_deg: float = 0.0
    speed_kmh: float = 0.0
    battery_pct: float = 100.0


class UnitResponse(BaseModel):
    unit_id: str
    callsign: str
    unit_type: str
    sector: str
    status: str
    lat: float
    lng: float
    altitude_m: float
    heading_deg: float
    speed_kmh: float
    battery_pct: float
    last_seen: datetime


class TrackPoint(BaseModel):
    lat: float
    lng: float
    ts: datetime


@router.post("/{unit_id}/position")
async def update_position(
    unit_id: str,
    position: PositionUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("map:rw"))
):
    """Update unit GPS position"""
    # Get unit from database
    result = await db.execute(select(Unit).where(Unit.unit_id == unit_id))
    unit = result.scalar_one_or_none()

    if not unit:
        raise HTTPException(status_code=404, detail="Unit not found")

    # Update Redis cache (with TTL)
    position_data = {
        "unit_id": unit_id,
        "lat": position.lat,
        "lng": position.lng,
        "altitude_m": position.altitude_m,
        "heading_deg": position.heading_deg,
        "speed_kmh": position.speed_kmh,
        "battery_pct": position.battery_pct,
        "ts": datetime.utcnow().isoformat()
    }
    await set_unit_position(unit_id, position_data)

    # Write to InfluxDB for time-series tracking
    async with InfluxDBClientAsync(
        url=settings.INFLUX_URL,
        token=settings.INFLUX_TOKEN,
        org=settings.INFLUX_ORG
    ) as client:
        write_api = client.write_api()

        point = Point("gps_telemetry") \
            .tag("unit_id", unit_id) \
            .tag("unit_type", unit.unit_type) \
            .field("lat", position.lat) \
            .field("lng", position.lng) \
            .field("altitude_m", position.altitude_m) \
            .field("heading_deg", position.heading_deg) \
            .field("speed_kmh", position.speed_kmh) \
            .field("battery_pct", position.battery_pct) \
            .time(datetime.utcnow())

        await write_api.write(bucket=settings.INFLUX_BUCKET_GPS, record=point)

    # Update PostgreSQL
    await db.execute(
        update(Unit)
        .where(Unit.unit_id == unit_id)
        .values(
            lat=position.lat,
            lng=position.lng,
            altitude_m=position.altitude_m,
            heading_deg=position.heading_deg,
            speed_kmh=position.speed_kmh,
            battery_pct=position.battery_pct,
            last_seen=datetime.utcnow()
        )
    )
    await db.commit()

    return {"message": "Position updated", "unit_id": unit_id}


@router.get("/{unit_id}/track", response_model=List[TrackPoint])
async def get_track_history(
    unit_id: str,
    hours: int = 24,
    user: User = Depends(require_permission("map:r"))
):
    """Get historical GPS track for unit"""
    async with InfluxDBClientAsync(
        url=settings.INFLUX_URL,
        token=settings.INFLUX_TOKEN,
        org=settings.INFLUX_ORG
    ) as client:
        query_api = client.query_api()

        # Flux query
        flux_query = f'''
        from(bucket: "{settings.INFLUX_BUCKET_GPS}")
          |> range(start: -{hours}h)
          |> filter(fn: (r) => r["_measurement"] == "gps_telemetry")
          |> filter(fn: (r) => r["unit_id"] == "{unit_id}")
          |> filter(fn: (r) => r["_field"] == "lat" or r["_field"] == "lng")
          |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
          |> sort(columns: ["_time"])
        '''

        tables = await query_api.query(flux_query)

        track_points = []
        for table in tables:
            for record in table.records:
                track_points.append(TrackPoint(
                    lat=record["lat"],
                    lng=record["lng"],
                    ts=record["_time"]
                ))

        return track_points


@router.get("/", response_model=List[UnitResponse])
async def list_units(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("map:r"))
):
    """Get all units"""
    result = await db.execute(select(Unit).where(Unit.is_active == True))
    units = result.scalars().all()

    return [
        UnitResponse(
            unit_id=u.unit_id,
            callsign=u.callsign,
            unit_type=u.unit_type,
            sector=u.sector,
            status=u.status,
            lat=u.lat,
            lng=u.lng,
            altitude_m=u.altitude_m,
            heading_deg=u.heading_deg,
            speed_kmh=u.speed_kmh,
            battery_pct=u.battery_pct,
            last_seen=u.last_seen
        )
        for u in units
    ]


@router.websocket("/stream/live")
async def stream_live_positions(websocket: WebSocket):
    """WebSocket endpoint for real-time GPS updates"""
    await websocket.accept()

    try:
        # Send initial snapshot
        positions = await get_all_unit_positions()
        await websocket.send_json({
            "type": "snapshot",
            "data": positions
        })

        # Subscribe to live updates
        async for update in subscribe_channel("gps.live"):
            await websocket.send_json({
                "type": "update",
                "data": update
            })

    except WebSocketDisconnect:
        pass
    except Exception as e:
        await websocket.close(code=1011, reason=str(e))
