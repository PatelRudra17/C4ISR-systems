from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta

from app.core.database import get_db
from app.core.redis_client import publish_event
from app.models.models import CyberEvent, BlockedIP, ThreatSeverity, User
from app.routers.auth import get_current_user, require_permission

router = APIRouter(prefix="/api/v1/cyber", tags=["Cyber Security"])


class CyberEventCreate(BaseModel):
    event_type: str
    severity: ThreatSeverity
    source_ip: str
    dest_ip: Optional[str] = None
    dest_port: Optional[int] = None
    protocol: Optional[str] = None
    description: str
    is_blocked: bool = False
    raw_payload: Optional[str] = None


class CyberEventResponse(BaseModel):
    id: str
    event_type: str
    severity: str
    source_ip: str
    dest_ip: Optional[str]
    dest_port: Optional[int]
    description: str
    is_blocked: bool
    detected_at: datetime


class BlockIPRequest(BaseModel):
    ip_address: str
    reason: str
    expires_hours: Optional[int] = None


class BlockedIPResponse(BaseModel):
    id: str
    ip_address: str
    reason: str
    blocked_at: datetime
    expires_at: Optional[datetime]


@router.post("/event", response_model=CyberEventResponse)
async def create_cyber_event(
    event: CyberEventCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("cyber:rw"))
):
    """Log new cyber security event"""
    new_event = CyberEvent(
        event_type=event.event_type,
        severity=event.severity,
        source_ip=event.source_ip,
        dest_ip=event.dest_ip,
        dest_port=event.dest_port,
        protocol=event.protocol,
        description=event.description,
        is_blocked=event.is_blocked,
        blocked_by=user.id if event.is_blocked else None,
        raw_payload=event.raw_payload
    )

    db.add(new_event)
    await db.commit()
    await db.refresh(new_event)

    # Publish to Redis for real-time alerts
    await publish_event("cyber.events", {
        "event_id": str(new_event.id),
        "event_type": event.event_type,
        "severity": event.severity.value,
        "source_ip": event.source_ip,
        "description": event.description,
        "is_blocked": event.is_blocked,
        "detected_at": new_event.detected_at.isoformat()
    })

    return CyberEventResponse(
        id=str(new_event.id),
        event_type=new_event.event_type,
        severity=new_event.severity.value,
        source_ip=new_event.source_ip,
        dest_ip=new_event.dest_ip,
        dest_port=new_event.dest_port,
        description=new_event.description,
        is_blocked=new_event.is_blocked,
        detected_at=new_event.detected_at
    )


@router.get("/events", response_model=List[CyberEventResponse])
async def list_cyber_events(
    limit: int = 100,
    severity: Optional[ThreatSeverity] = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("cyber:r"))
):
    """List recent cyber security events"""
    query = select(CyberEvent).order_by(desc(CyberEvent.detected_at)).limit(limit)

    if severity:
        query = query.where(CyberEvent.severity == severity)

    result = await db.execute(query)
    events = result.scalars().all()

    return [
        CyberEventResponse(
            id=str(e.id),
            event_type=e.event_type,
            severity=e.severity.value,
            source_ip=e.source_ip,
            dest_ip=e.dest_ip,
            dest_port=e.dest_port,
            description=e.description,
            is_blocked=e.is_blocked,
            detected_at=e.detected_at
        )
        for e in events
    ]


@router.post("/block-ip", response_model=BlockedIPResponse)
async def block_ip(
    block_request: BlockIPRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("cyber:rw"))
):
    """Block an IP address"""
    # Check if IP already blocked
    result = await db.execute(
        select(BlockedIP).where(BlockedIP.ip_address == block_request.ip_address)
    )
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(status_code=400, detail="IP already blocked")

    # Calculate expiration
    expires_at = None
    if block_request.expires_hours:
        expires_at = datetime.utcnow() + timedelta(hours=block_request.expires_hours)

    # Create block entry
    blocked_ip = BlockedIP(
        ip_address=block_request.ip_address,
        reason=block_request.reason,
        blocked_by=user.id,
        expires_at=expires_at
    )

    db.add(blocked_ip)
    await db.commit()
    await db.refresh(blocked_ip)

    # Publish to Redis
    await publish_event("cyber.ip_blocked", {
        "ip_address": block_request.ip_address,
        "reason": block_request.reason,
        "blocked_by": user.callsign,
        "expires_at": expires_at.isoformat() if expires_at else None
    })

    return BlockedIPResponse(
        id=str(blocked_ip.id),
        ip_address=blocked_ip.ip_address,
        reason=blocked_ip.reason,
        blocked_at=blocked_ip.created_at,
        expires_at=blocked_ip.expires_at
    )


@router.get("/blocked-ips", response_model=List[BlockedIPResponse])
async def list_blocked_ips(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("cyber:r"))
):
    """List all blocked IP addresses"""
    # Only return non-expired blocks
    result = await db.execute(
        select(BlockedIP).where(
            (BlockedIP.expires_at == None) |
            (BlockedIP.expires_at > datetime.utcnow())
        )
    )
    blocked_ips = result.scalars().all()

    return [
        BlockedIPResponse(
            id=str(b.id),
            ip_address=b.ip_address,
            reason=b.reason,
            blocked_at=b.created_at,
            expires_at=b.expires_at
        )
        for b in blocked_ips
    ]


@router.delete("/unblock-ip/{ip_address}")
async def unblock_ip(
    ip_address: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("cyber:rw"))
):
    """Unblock an IP address"""
    result = await db.execute(
        select(BlockedIP).where(BlockedIP.ip_address == ip_address)
    )
    blocked = result.scalar_one_or_none()

    if not blocked:
        raise HTTPException(status_code=404, detail="IP not found in block list")

    await db.delete(blocked)
    await db.commit()

    return {"message": "IP unblocked", "ip_address": ip_address}


@router.get("/stats")
async def get_cyber_stats(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("cyber:r"))
):
    """Get cyber security statistics"""
    # Count events by severity
    events_result = await db.execute(
        select(
            CyberEvent.severity,
            func.count(CyberEvent.id).label("count")
        )
        .group_by(CyberEvent.severity)
    )

    events_by_severity = {}
    for row in events_result:
        events_by_severity[row[0].value] = row[1]

    # Count blocked IPs
    blocked_ips_result = await db.execute(
        select(func.count(BlockedIP.id))
    )
    blocked_ips_count = blocked_ips_result.scalar()

    # Count events blocked today
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    blocked_today_result = await db.execute(
        select(func.count(CyberEvent.id))
        .where(CyberEvent.is_blocked == True)
        .where(CyberEvent.detected_at >= today_start)
    )
    blocked_today = blocked_today_result.scalar()

    return {
        "events_by_severity": events_by_severity,
        "blocked_ips_count": blocked_ips_count,
        "blocked_today": blocked_today,
        "total_events": sum(events_by_severity.values())
    }
