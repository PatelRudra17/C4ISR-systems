import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime,
    ForeignKey, Text, JSON, Enum, ARRAY
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum
from app.core.database import Base


# Enums
class UserRole(str, enum.Enum):
    COMMANDER = "COMMANDER"
    OPERATOR = "OPERATOR"
    ANALYST = "ANALYST"
    VIEWER = "VIEWER"


class ClearanceLevel(str, enum.Enum):
    TOP_SECRET = "TOP SECRET"
    SECRET = "SECRET"
    CONFIDENTIAL = "CONFIDENTIAL"
    UNCLASSIFIED = "UNCLASSIFIED"


class ThreatSeverity(str, enum.Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class ThreatStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    INVESTIGATING = "INVESTIGATING"
    NEUTRALIZED = "NEUTRALIZED"
    FALSE_POSITIVE = "FALSE_POSITIVE"


class DroneStatus(str, enum.Enum):
    AIRBORNE = "AIRBORNE"
    READY = "READY"
    CHARGING = "CHARGING"
    MAINTENANCE = "MAINTENANCE"
    OFFLINE = "OFFLINE"


class MissionStatus(str, enum.Enum):
    PLANNED = "PLANNED"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    ABORTED = "ABORTED"
    ON_HOLD = "ON_HOLD"


class ChannelType(str, enum.Enum):
    COMMAND = "COMMAND"
    TACTICAL = "TACTICAL"
    INTEL = "INTEL"
    EMERGENCY = "EMERGENCY"
    GENERAL = "GENERAL"


# Models
class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    callsign = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False)
    full_name = Column(String(255), nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.VIEWER)
    clearance = Column(Enum(ClearanceLevel), nullable=False, default=ClearanceLevel.UNCLASSIFIED)
    totp_secret = Column(String(32), nullable=True)
    mfa_enabled = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    last_login = Column(DateTime, nullable=True)
    login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    units_commanded = relationship("Unit", back_populates="commander", foreign_keys="Unit.commander_id")
    threats_resolved = relationship("Threat", back_populates="resolver", foreign_keys="Threat.resolved_by")
    drones_operated = relationship("Drone", back_populates="operator", foreign_keys="Drone.operator_id")
    missions_commanded = relationship("Mission", back_populates="commander", foreign_keys="Mission.commander_id")
    messages_sent = relationship("Message", back_populates="sender", foreign_keys="Message.sender_id")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    action = Column(String(100), nullable=False)
    resource = Column(String(255), nullable=False)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    status_code = Column(Integer, nullable=True)
    details = Column(JSON, nullable=True)
    hash = Column(String(64), nullable=False)  # SHA-256 for tamper detection
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)


class Unit(Base):
    __tablename__ = "units"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    unit_id = Column(String(50), unique=True, nullable=False, index=True)
    callsign = Column(String(50), nullable=False)
    unit_type = Column(String(50), nullable=False)  # INFANTRY, ARMOR, ARTILLERY, etc.
    sector = Column(String(10), nullable=False)
    status = Column(String(20), default="ACTIVE")
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    altitude_m = Column(Float, default=0.0)
    heading_deg = Column(Float, default=0.0)
    speed_kmh = Column(Float, default=0.0)
    battery_pct = Column(Float, default=100.0)
    commander_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    last_seen = Column(DateTime, default=datetime.utcnow)

    # Relationships
    commander = relationship("User", back_populates="units_commanded", foreign_keys=[commander_id])


class Threat(Base):
    __tablename__ = "threats"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    threat_id = Column(String(50), unique=True, nullable=False, index=True)
    threat_type = Column(String(50), nullable=False)  # VEHICLE, PERSONNEL, SIGNAL, etc.
    severity = Column(Enum(ThreatSeverity), nullable=False)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    sector = Column(String(10), nullable=False)
    ai_confidence = Column(Float, nullable=False)  # 0.0 - 1.0
    ai_model = Column(String(100), nullable=True)
    sensor_source = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(Enum(ThreatStatus), default=ThreatStatus.ACTIVE)
    detected_at = Column(DateTime, default=datetime.utcnow, index=True)
    resolved_at = Column(DateTime, nullable=True)
    resolved_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    image_path = Column(String(500), nullable=True)
    metadata = Column(JSON, nullable=True)

    # Relationships
    resolver = relationship("User", back_populates="threats_resolved", foreign_keys=[resolved_by])


class Drone(Base):
    __tablename__ = "drones"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    drone_id = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    model = Column(String(100), nullable=False)
    sysid = Column(Integer, nullable=False)  # MAVLink system ID
    status = Column(Enum(DroneStatus), default=DroneStatus.OFFLINE)
    lat = Column(Float, default=0.0)
    lng = Column(Float, default=0.0)
    altitude_m = Column(Float, default=0.0)
    speed_ms = Column(Float, default=0.0)
    heading_deg = Column(Float, default=0.0)
    battery_pct = Column(Float, default=0.0)
    battery_voltage = Column(Float, default=0.0)
    gps_fix = Column(Integer, default=0)
    satellites = Column(Integer, default=0)
    flight_mode = Column(String(50), default="STABILIZE")
    is_armed = Column(Boolean, default=False)
    operator_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    active_mission = Column(String(50), nullable=True)
    geofence_enabled = Column(Boolean, default=True)
    total_flight_hrs = Column(Float, default=0.0)
    last_heartbeat = Column(DateTime, nullable=True)

    # Relationships
    operator = relationship("User", back_populates="drones_operated", foreign_keys=[operator_id])
    missions = relationship("DroneMission", back_populates="drone")


class DroneMission(Base):
    __tablename__ = "drone_missions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    mission_id = Column(String(50), unique=True, nullable=False, index=True)
    drone_id = Column(UUID(as_uuid=True), ForeignKey("drones.id"), nullable=False)
    name = Column(String(255), nullable=False)
    mission_type = Column(String(50), nullable=False)  # RECON, STRIKE, ESCORT, etc.
    waypoints = Column(JSON, nullable=False)  # [{lat, lng, alt, action}, ...]
    status = Column(Enum(MissionStatus), default=MissionStatus.PLANNED)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    drone = relationship("Drone", back_populates="missions")


class Channel(Base):
    __tablename__ = "channels"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    channel_type = Column(Enum(ChannelType), nullable=False)
    classification = Column(Enum(ClearanceLevel), default=ClearanceLevel.UNCLASSIFIED)
    min_role = Column(Enum(UserRole), default=UserRole.VIEWER)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    messages = relationship("Message", back_populates="channel")


class Message(Base):
    __tablename__ = "messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    channel_id = Column(UUID(as_uuid=True), ForeignKey("channels.id"), nullable=False)
    sender_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    ciphertext = Column(Text, nullable=False)  # AES-256 encrypted
    iv = Column(String(64), nullable=False)  # Initialization vector (base64)
    classification = Column(Enum(ClearanceLevel), default=ClearanceLevel.UNCLASSIFIED)
    msg_type = Column(String(20), default="TEXT")  # TEXT, FILE, IMAGE, etc.
    file_path = Column(String(500), nullable=True)
    is_deleted = Column(Boolean, default=False)
    sent_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Relationships
    channel = relationship("Channel", back_populates="messages")
    sender = relationship("User", back_populates="messages_sent", foreign_keys=[sender_id])


class Mission(Base):
    __tablename__ = "missions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    mission_id = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    mission_type = Column(String(50), nullable=False)
    sector = Column(String(10), nullable=False)
    classification = Column(Enum(ClearanceLevel), default=ClearanceLevel.SECRET)
    status = Column(Enum(MissionStatus), default=MissionStatus.PLANNED)
    commander_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    units_assigned = Column(ARRAY(String), default=[])
    drones_assigned = Column(ARRAY(String), default=[])
    objectives = Column(JSON, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    commander = relationship("User", back_populates="missions_commanded", foreign_keys=[commander_id])


class CyberEvent(Base):
    __tablename__ = "cyber_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_type = Column(String(50), nullable=False)
    severity = Column(Enum(ThreatSeverity), nullable=False)
    source_ip = Column(String(45), nullable=False)
    dest_ip = Column(String(45), nullable=True)
    dest_port = Column(Integer, nullable=True)
    protocol = Column(String(20), nullable=True)
    description = Column(Text, nullable=False)
    is_blocked = Column(Boolean, default=False)
    blocked_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    raw_payload = Column(Text, nullable=True)
    detected_at = Column(DateTime, default=datetime.utcnow, index=True)


class BlockedIP(Base):
    __tablename__ = "blocked_ips"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ip_address = Column(String(45), unique=True, nullable=False, index=True)
    reason = Column(Text, nullable=False)
    blocked_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
