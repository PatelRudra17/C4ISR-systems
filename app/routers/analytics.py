from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel
from typing import List, Dict
from datetime import datetime
import psutil
from influxdb_client.client.influxdb_client_async import InfluxDBClientAsync

from app.core.database import get_db
from app.core.config import get_settings
from app.models.models import Threat, ThreatSeverity, User
from app.routers.auth import get_current_user, require_permission

settings = get_settings()
router = APIRouter(prefix="/api/v1/analytics", tags=["Analytics"])


class GPSHistoryPoint(BaseModel):
    lat: float
    lng: float
    speed_kmh: float
    ts: datetime


class ThreatStats(BaseModel):
    severity: str
    count: int


class SystemHealth(BaseModel):
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    network_sent_mb: float
    network_recv_mb: float


@router.get("/gps/history", response_model=List[GPSHistoryPoint])
async def get_gps_history(
    unit_id: str,
    hours: int = 24,
    user: User = Depends(require_permission("analytics:r"))
):
    """Get GPS history from InfluxDB"""
    async with InfluxDBClientAsync(
        url=settings.INFLUX_URL,
        token=settings.INFLUX_TOKEN,
        org=settings.INFLUX_ORG
    ) as client:
        query_api = client.query_api()

        flux_query = f'''
        from(bucket: "{settings.INFLUX_BUCKET_GPS}")
          |> range(start: -{hours}h)
          |> filter(fn: (r) => r["_measurement"] == "gps_telemetry")
          |> filter(fn: (r) => r["unit_id"] == "{unit_id}")
          |> filter(fn: (r) => r["_field"] == "lat" or r["_field"] == "lng" or r["_field"] == "speed_kmh")
          |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
          |> sort(columns: ["_time"])
        '''

        tables = await query_api.query(flux_query)

        points = []
        for table in tables:
            for record in table.records:
                points.append(GPSHistoryPoint(
                    lat=record["lat"],
                    lng=record["lng"],
                    speed_kmh=record.get("speed_kmh", 0.0),
                    ts=record["_time"]
                ))

        return points


@router.get("/threats/stats", response_model=List[ThreatStats])
async def get_threat_stats(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("analytics:r"))
):
    """Get threat statistics by severity"""
    # Query PostgreSQL for threat counts by severity
    result = await db.execute(
        select(
            Threat.severity,
            func.count(Threat.id).label("count")
        )
        .group_by(Threat.severity)
    )

    stats = []
    for row in result:
        stats.append(ThreatStats(
            severity=row[0].value,
            count=row[1]
        ))

    return stats


@router.get("/threats/influx-stats")
async def get_threat_influx_stats(
    hours: int = 24,
    user: User = Depends(require_permission("analytics:r"))
):
    """Get threat statistics from InfluxDB time-series data"""
    async with InfluxDBClientAsync(
        url=settings.INFLUX_URL,
        token=settings.INFLUX_TOKEN,
        org=settings.INFLUX_ORG
    ) as client:
        query_api = client.query_api()

        flux_query = f'''
        from(bucket: "{settings.INFLUX_BUCKET_THREAT}")
          |> range(start: -{hours}h)
          |> filter(fn: (r) => r["_measurement"] == "threat_events")
          |> group(columns: ["severity"])
          |> count()
        '''

        tables = await query_api.query(flux_query)

        stats = {}
        for table in tables:
            for record in table.records:
                severity = record.values.get("severity", "UNKNOWN")
                count = record.get_value()
                stats[severity] = count

        return stats


@router.get("/system/health", response_model=SystemHealth)
async def get_system_health(
    user: User = Depends(require_permission("analytics:r"))
):
    """Get real-time system health metrics using psutil"""
    # CPU usage
    cpu_percent = psutil.cpu_percent(interval=0.5)

    # Memory usage
    memory = psutil.virtual_memory()
    memory_percent = memory.percent

    # Disk usage
    disk = psutil.disk_usage("/")
    disk_percent = disk.percent

    # Network I/O
    net_io = psutil.net_io_counters()
    network_sent_mb = net_io.bytes_sent / (1024 * 1024)
    network_recv_mb = net_io.bytes_recv / (1024 * 1024)

    return SystemHealth(
        cpu_percent=cpu_percent,
        memory_percent=memory_percent,
        disk_percent=disk_percent,
        network_sent_mb=round(network_sent_mb, 2),
        network_recv_mb=round(network_recv_mb, 2)
    )


@router.get("/missions/summary")
async def get_missions_summary(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("analytics:r"))
):
    """Get mission statistics summary"""
    from app.models.models import Mission, MissionStatus

    # Count missions by status
    result = await db.execute(
        select(
            Mission.status,
            func.count(Mission.id).label("count")
        )
        .group_by(Mission.status)
    )

    stats = {}
    for row in result:
        stats[row[0].value] = row[1]

    return {
        "total": sum(stats.values()),
        "by_status": stats
    }
