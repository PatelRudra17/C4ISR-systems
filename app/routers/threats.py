from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from influxdb_client import Point
from influxdb_client.client.influxdb_client_async import InfluxDBClientAsync

from app.core.database import get_db
from app.core.redis_client import set_active_threat, get_active_threats
from app.core.config import get_settings
from app.models.models import Threat, ThreatSeverity, ThreatStatus, User
from app.routers.auth import get_current_user, require_permission

settings = get_settings()
router = APIRouter(prefix="/api/v1/threats", tags=["Threats"])


class ThreatCreate(BaseModel):
    threat_type: str
    severity: ThreatSeverity
    lat: float
    lng: float
    sector: str
    ai_confidence: float
    ai_model: Optional[str] = None
    sensor_source: str
    description: Optional[str] = None
    image_path: Optional[str] = None
    metadata: Optional[dict] = None


class ThreatResponse(BaseModel):
    threat_id: str
    threat_type: str
    severity: str
    lat: float
    lng: float
    sector: str
    ai_confidence: float
    sensor_source: str
    description: Optional[str]
    status: str
    detected_at: datetime


class ThreatResolve(BaseModel):
    status: ThreatStatus
    notes: Optional[str] = None


@router.post("/", response_model=ThreatResponse)
async def create_threat(
    threat: ThreatCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("threats:rw"))
):
    """Create new threat detection"""
    # Generate threat ID
    threat_id = f"THR-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

    # Create database entry
    new_threat = Threat(
        threat_id=threat_id,
        threat_type=threat.threat_type,
        severity=threat.severity,
        lat=threat.lat,
        lng=threat.lng,
        sector=threat.sector,
        ai_confidence=threat.ai_confidence,
        ai_model=threat.ai_model,
        sensor_source=threat.sensor_source,
        description=threat.description,
        image_path=threat.image_path,
        metadata=threat.metadata,
        status=ThreatStatus.ACTIVE
    )

    db.add(new_threat)
    await db.commit()
    await db.refresh(new_threat)

    # Cache active threat in Redis
    threat_data = {
        "threat_id": threat_id,
        "threat_type": threat.threat_type,
        "severity": threat.severity.value,
        "lat": threat.lat,
        "lng": threat.lng,
        "sector": threat.sector,
        "ai_confidence": threat.ai_confidence,
        "detected_at": datetime.utcnow().isoformat()
    }
    await set_active_threat(threat_id, threat_data)

    # Write to InfluxDB
    async with InfluxDBClientAsync(
        url=settings.INFLUX_URL,
        token=settings.INFLUX_TOKEN,
        org=settings.INFLUX_ORG
    ) as client:
        write_api = client.write_api()

        point = Point("threat_events") \
            .tag("threat_id", threat_id) \
            .tag("threat_type", threat.threat_type) \
            .tag("severity", threat.severity.value) \
            .tag("sector", threat.sector) \
            .field("lat", threat.lat) \
            .field("lng", threat.lng) \
            .field("ai_confidence", threat.ai_confidence) \
            .time(datetime.utcnow())

        await write_api.write(bucket=settings.INFLUX_BUCKET_THREAT, record=point)

    return ThreatResponse(
        threat_id=threat_id,
        threat_type=new_threat.threat_type,
        severity=new_threat.severity.value,
        lat=new_threat.lat,
        lng=new_threat.lng,
        sector=new_threat.sector,
        ai_confidence=new_threat.ai_confidence,
        sensor_source=new_threat.sensor_source,
        description=new_threat.description,
        status=new_threat.status.value,
        detected_at=new_threat.detected_at
    )


@router.get("/", response_model=List[ThreatResponse])
async def list_threats(
    limit: int = 100,
    severity: Optional[ThreatSeverity] = None,
    status: Optional[ThreatStatus] = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("threats:r"))
):
    """List threats with optional filters"""
    query = select(Threat).order_by(desc(Threat.detected_at)).limit(limit)

    if severity:
        query = query.where(Threat.severity == severity)
    if status:
        query = query.where(Threat.status == status)

    result = await db.execute(query)
    threats = result.scalars().all()

    return [
        ThreatResponse(
            threat_id=t.threat_id,
            threat_type=t.threat_type,
            severity=t.severity.value,
            lat=t.lat,
            lng=t.lng,
            sector=t.sector,
            ai_confidence=t.ai_confidence,
            sensor_source=t.sensor_source,
            description=t.description,
            status=t.status.value,
            detected_at=t.detected_at
        )
        for t in threats
    ]


@router.get("/active")
async def get_active_threats_cached(
    user: User = Depends(require_permission("threats:r"))
):
    """Get active threats from Redis cache"""
    threats = await get_active_threats()
    return {"count": len(threats), "threats": threats}


@router.patch("/{threat_id}/resolve")
async def resolve_threat(
    threat_id: str,
    resolve_data: ThreatResolve,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("threats:rw"))
):
    """Mark threat as resolved/neutralized"""
    result = await db.execute(select(Threat).where(Threat.threat_id == threat_id))
    threat = result.scalar_one_or_none()

    if not threat:
        raise HTTPException(status_code=404, detail="Threat not found")

    threat.status = resolve_data.status
    threat.resolved_at = datetime.utcnow()
    threat.resolved_by = user.id

    if resolve_data.notes:
        if not threat.metadata:
            threat.metadata = {}
        threat.metadata["resolution_notes"] = resolve_data.notes

    await db.commit()

    return {"message": "Threat resolved", "threat_id": threat_id}
