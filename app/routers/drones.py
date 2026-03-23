from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime

from app.core.database import get_db
from app.core.redis_client import subscribe_channel
from app.models.models import Drone, DroneStatus, DroneMission, MissionStatus, User
from app.routers.auth import get_current_user, require_permission
from app.services.mavlink_service import drone_manager

router = APIRouter(prefix="/api/v1/drones", tags=["Drones"])


class DroneResponse(BaseModel):
    drone_id: str
    name: str
    model: str
    status: str
    lat: float
    lng: float
    altitude_m: float
    speed_ms: float
    heading_deg: float
    battery_pct: float
    flight_mode: str
    is_armed: bool


class DroneCommand(BaseModel):
    command: str  # ARM, DISARM, TAKEOFF, LAND, RTH, GOTO, MODE, SPEED
    lat: Optional[float] = None
    lng: Optional[float] = None
    altitude: Optional[float] = None
    mode: Optional[str] = None
    speed_ms: Optional[float] = None


class MissionCreate(BaseModel):
    drone_id: str
    name: str
    mission_type: str
    waypoints: List[Dict]  # [{lat, lng, alt, action}, ...]


class MissionResponse(BaseModel):
    mission_id: str
    name: str
    mission_type: str
    status: str
    waypoints: List[Dict]
    created_at: datetime


@router.get("/", response_model=List[DroneResponse])
async def list_drones(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("drones:r"))
):
    """List all drones"""
    result = await db.execute(select(Drone))
    drones = result.scalars().all()

    return [
        DroneResponse(
            drone_id=d.drone_id,
            name=d.name,
            model=d.model,
            status=d.status.value,
            lat=d.lat,
            lng=d.lng,
            altitude_m=d.altitude_m,
            speed_ms=d.speed_ms,
            heading_deg=d.heading_deg,
            battery_pct=d.battery_pct,
            flight_mode=d.flight_mode,
            is_armed=d.is_armed
        )
        for d in drones
    ]


@router.get("/{drone_id}", response_model=DroneResponse)
async def get_drone(
    drone_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("drones:r"))
):
    """Get specific drone details"""
    result = await db.execute(select(Drone).where(Drone.drone_id == drone_id))
    drone = result.scalar_one_or_none()

    if not drone:
        raise HTTPException(status_code=404, detail="Drone not found")

    # Try to get live state from MAVLink manager
    state = drone_manager.get_state(drone_id)

    if state:
        return DroneResponse(
            drone_id=state.drone_id,
            name=drone.name,
            model=drone.model,
            status=drone.status.value,
            lat=state.lat,
            lng=state.lng,
            altitude_m=state.altitude_m,
            speed_ms=state.speed_ms,
            heading_deg=state.heading_deg,
            battery_pct=state.battery_pct,
            flight_mode=state.flight_mode,
            is_armed=state.is_armed
        )

    return DroneResponse(
        drone_id=drone.drone_id,
        name=drone.name,
        model=drone.model,
        status=drone.status.value,
        lat=drone.lat,
        lng=drone.lng,
        altitude_m=drone.altitude_m,
        speed_ms=drone.speed_ms,
        heading_deg=drone.heading_deg,
        battery_pct=drone.battery_pct,
        flight_mode=drone.flight_mode,
        is_armed=drone.is_armed
    )


@router.post("/{drone_id}/command")
async def send_command(
    drone_id: str,
    command: DroneCommand,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("drones:rw"))
):
    """Send command to drone"""
    # Get drone from database
    result = await db.execute(select(Drone).where(Drone.drone_id == drone_id))
    drone = result.scalar_one_or_none()

    if not drone:
        raise HTTPException(status_code=404, detail="Drone not found")

    sysid = drone.sysid
    success = False

    # Execute command
    if command.command == "ARM":
        success = await drone_manager.arm(sysid)
    elif command.command == "DISARM":
        success = await drone_manager.disarm(sysid)
    elif command.command == "TAKEOFF":
        alt = command.altitude or 10.0
        success = await drone_manager.takeoff(sysid, alt)
    elif command.command == "LAND":
        success = await drone_manager.land(sysid)
    elif command.command == "RTH":
        success = await drone_manager.return_to_home(sysid)
    elif command.command == "GOTO":
        if not command.lat or not command.lng:
            raise HTTPException(status_code=400, detail="GOTO requires lat/lng")
        alt = command.altitude or 50.0
        success = await drone_manager.goto(sysid, command.lat, command.lng, alt)
    elif command.command == "MODE":
        if not command.mode:
            raise HTTPException(status_code=400, detail="MODE requires mode string")
        success = await drone_manager.set_mode(sysid, command.mode)
    elif command.command == "SPEED":
        if not command.speed_ms:
            raise HTTPException(status_code=400, detail="SPEED requires speed_ms")
        success = await drone_manager.set_speed(sysid, command.speed_ms)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown command: {command.command}")

    if not success:
        raise HTTPException(status_code=500, detail="Command failed")

    return {"message": f"Command {command.command} sent", "drone_id": drone_id}


@router.post("/mission", response_model=MissionResponse)
async def create_mission(
    mission: MissionCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("drones:rw"))
):
    """Create and upload drone mission"""
    # Get drone
    result = await db.execute(select(Drone).where(Drone.drone_id == mission.drone_id))
    drone = result.scalar_one_or_none()

    if not drone:
        raise HTTPException(status_code=404, detail="Drone not found")

    # Validate waypoints
    for wp in mission.waypoints:
        if "lat" not in wp or "lng" not in wp:
            raise HTTPException(status_code=400, detail="Each waypoint must have lat/lng")

    # Generate mission ID
    mission_id = f"MSN-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

    # Upload mission to drone
    success = await drone_manager.upload_mission(drone.sysid, mission.waypoints)

    if not success:
        raise HTTPException(status_code=500, detail="Failed to upload mission")

    # Save mission to database
    new_mission = DroneMission(
        mission_id=mission_id,
        drone_id=drone.id,
        name=mission.name,
        mission_type=mission.mission_type,
        waypoints=mission.waypoints,
        status=MissionStatus.PLANNED,
        created_by=user.id
    )

    db.add(new_mission)
    await db.commit()
    await db.refresh(new_mission)

    # Update drone
    drone.active_mission = mission_id
    await db.commit()

    return MissionResponse(
        mission_id=mission_id,
        name=new_mission.name,
        mission_type=new_mission.mission_type,
        status=new_mission.status.value,
        waypoints=new_mission.waypoints,
        created_at=new_mission.created_at
    )


@router.websocket("/{drone_id}/stream")
async def stream_drone_telemetry(websocket: WebSocket, drone_id: str):
    """WebSocket stream for live drone telemetry"""
    await websocket.accept()

    try:
        # Subscribe to drone GPS updates
        async for update in subscribe_channel("drones.gps"):
            if update.get("drone_id") == drone_id:
                await websocket.send_json({
                    "type": "telemetry",
                    "data": update
                })

    except WebSocketDisconnect:
        pass
    except Exception as e:
        await websocket.close(code=1011, reason=str(e))
