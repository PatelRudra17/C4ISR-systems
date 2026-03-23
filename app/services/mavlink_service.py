import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional, List
from pymavlink import mavutil
import structlog

from app.core.redis_client import cache_set, publish_event
from app.core.config import get_settings

settings = get_settings()
logger = structlog.get_logger()


@dataclass
class DroneState:
    """Current state of a drone"""
    drone_id: str
    sysid: int
    lat: float = 0.0
    lng: float = 0.0
    altitude_m: float = 0.0
    speed_ms: float = 0.0
    heading_deg: float = 0.0
    battery_pct: float = 0.0
    battery_voltage: float = 0.0
    gps_fix: int = 0
    satellites: int = 0
    roll_deg: float = 0.0
    pitch_deg: float = 0.0
    yaw_deg: float = 0.0
    flight_mode: str = "UNKNOWN"
    is_armed: bool = False
    last_heartbeat: Optional[datetime] = None


class MAVLinkDroneManager:
    """Manages MAVLink connections to multiple drones"""

    def __init__(self):
        self.connections: Dict[int, mavutil.mavlink_connection] = {}
        self.drone_states: Dict[str, DroneState] = {}
        self.telemetry_tasks: Dict[int, asyncio.Task] = {}

    async def connect_drone(
        self,
        drone_id: str,
        sysid: int,
        connection_string: str = None
    ) -> bool:
        """
        Connect to a drone via MAVLink
        connection_string examples:
          - "udp:127.0.0.1:14550" (SITL simulator)
          - "tcp:192.168.1.100:5760" (companion computer)
          - "/dev/ttyUSB0" (serial telemetry)
        """
        if not connection_string:
            connection_string = f"udp:{settings.MAVLINK_HOST}:{settings.MAVLINK_PORT}"

        try:
            # Create MAVLink connection in thread pool
            loop = asyncio.get_event_loop()
            conn = await loop.run_in_executor(
                None,
                mavutil.mavlink_connection,
                connection_string
            )

            # Wait for heartbeat (10 second timeout)
            logger.info(f"Waiting for heartbeat from drone {drone_id} (sysid={sysid})...")
            heartbeat = await loop.run_in_executor(
                None,
                lambda: conn.wait_heartbeat(timeout=10)
            )

            if not heartbeat:
                logger.error(f"No heartbeat received from drone {drone_id}")
                return False

            self.connections[sysid] = conn
            self.drone_states[drone_id] = DroneState(drone_id=drone_id, sysid=sysid)

            # Request data streams
            await self._request_data_streams(conn, sysid)

            # Start telemetry loop
            task = asyncio.create_task(self._telemetry_loop(drone_id, sysid))
            self.telemetry_tasks[sysid] = task

            logger.info(f"Connected to drone {drone_id} (sysid={sysid})")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to drone {drone_id}: {e}")
            return False

    async def _request_data_streams(self, conn, sysid: int):
        """Request all MAVLink data streams at 10Hz"""
        loop = asyncio.get_event_loop()

        def request():
            # Request all message types
            conn.mav.request_data_stream_send(
                sysid,
                conn.target_component,
                mavutil.mavlink.MAV_DATA_STREAM_ALL,
                settings.DRONE_TELEMETRY_RATE,
                1
            )

        await loop.run_in_executor(None, request)

    async def _telemetry_loop(self, drone_id: str, sysid: int):
        """Continuously process telemetry from drone"""
        conn = self.connections[sysid]
        state = self.drone_states[drone_id]
        loop = asyncio.get_event_loop()

        logger.info(f"Starting telemetry loop for drone {drone_id}")

        while True:
            try:
                # Receive MAVLink message (non-blocking in thread pool)
                msg = await loop.run_in_executor(
                    None,
                    lambda: conn.recv_match(blocking=False, timeout=0.1)
                )

                if not msg:
                    await asyncio.sleep(0.01)
                    continue

                msg_type = msg.get_type()

                # Parse HEARTBEAT
                if msg_type == "HEARTBEAT":
                    state.is_armed = (msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED) != 0
                    state.flight_mode = mavutil.mode_string_v10(msg)
                    state.last_heartbeat = datetime.utcnow()

                # Parse GLOBAL_POSITION_INT
                elif msg_type == "GLOBAL_POSITION_INT":
                    state.lat = msg.lat / 1e7
                    state.lng = msg.lon / 1e7
                    state.altitude_m = msg.alt / 1000.0  # mm to meters
                    state.speed_ms = msg.vx / 100.0  # cm/s to m/s

                    # Publish GPS update to Redis
                    await publish_event("drones.gps", {
                        "drone_id": drone_id,
                        "lat": state.lat,
                        "lng": state.lng,
                        "altitude_m": state.altitude_m,
                        "speed_ms": state.speed_ms,
                        "ts": datetime.utcnow().isoformat()
                    })

                # Parse BATTERY_STATUS
                elif msg_type == "BATTERY_STATUS":
                    state.battery_pct = msg.battery_remaining
                    state.battery_voltage = msg.voltages[0] / 1000.0 if msg.voltages else 0.0

                # Parse GPS_RAW_INT
                elif msg_type == "GPS_RAW_INT":
                    state.gps_fix = msg.fix_type
                    state.satellites = msg.satellites_visible

                # Parse ATTITUDE
                elif msg_type == "ATTITUDE":
                    state.roll_deg = msg.roll * 57.2958  # radians to degrees
                    state.pitch_deg = msg.pitch * 57.2958
                    state.yaw_deg = msg.yaw * 57.2958
                    state.heading_deg = state.yaw_deg

                # Cache full state to Redis every second
                if int(datetime.utcnow().timestamp()) % 1 == 0:
                    await cache_set(
                        f"drone_state:{drone_id}",
                        state.__dict__,
                        settings.REDIS_TTL_DRONE
                    )

            except asyncio.CancelledError:
                logger.info(f"Telemetry loop cancelled for drone {drone_id}")
                break
            except Exception as e:
                logger.error(f"Error in telemetry loop for {drone_id}: {e}")
                await asyncio.sleep(1)

    async def arm(self, sysid: int) -> bool:
        """Arm the drone"""
        conn = self.connections.get(sysid)
        if not conn:
            return False

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, conn.arducopter_arm)
        return True

    async def disarm(self, sysid: int) -> bool:
        """Disarm the drone"""
        conn = self.connections.get(sysid)
        if not conn:
            return False

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, conn.arducopter_disarm)
        return True

    async def takeoff(self, sysid: int, altitude_m: float) -> bool:
        """Command drone to takeoff to specified altitude"""
        conn = self.connections.get(sysid)
        if not conn:
            return False

        loop = asyncio.get_event_loop()

        def send_takeoff():
            conn.mav.command_long_send(
                sysid,
                conn.target_component,
                mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
                0, 0, 0, 0, 0, 0, 0, altitude_m
            )

        await loop.run_in_executor(None, send_takeoff)
        return True

    async def land(self, sysid: int) -> bool:
        """Command drone to land"""
        conn = self.connections.get(sysid)
        if not conn:
            return False

        loop = asyncio.get_event_loop()

        def send_land():
            conn.mav.command_long_send(
                sysid,
                conn.target_component,
                mavutil.mavlink.MAV_CMD_NAV_LAND,
                0, 0, 0, 0, 0, 0, 0, 0
            )

        await loop.run_in_executor(None, send_land)
        return True

    async def return_to_home(self, sysid: int) -> bool:
        """Command drone to return to launch point"""
        conn = self.connections.get(sysid)
        if not conn:
            return False

        loop = asyncio.get_event_loop()

        def send_rth():
            conn.mav.command_long_send(
                sysid,
                conn.target_component,
                mavutil.mavlink.MAV_CMD_NAV_RETURN_TO_LAUNCH,
                0, 0, 0, 0, 0, 0, 0, 0
            )

        await loop.run_in_executor(None, send_rth)
        return True

    async def goto(self, sysid: int, lat: float, lng: float, altitude_m: float) -> bool:
        """Send goto waypoint command"""
        conn = self.connections.get(sysid)
        if not conn:
            return False

        loop = asyncio.get_event_loop()

        def send_goto():
            conn.mav.mission_item_int_send(
                sysid,
                conn.target_component,
                0,  # seq
                mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT,
                mavutil.mavlink.MAV_CMD_NAV_WAYPOINT,
                2,  # current (guided mode)
                1,  # autocontinue
                0, 0, 0, 0,  # params
                int(lat * 1e7),
                int(lng * 1e7),
                altitude_m
            )

        await loop.run_in_executor(None, send_goto)
        return True

    async def set_mode(self, sysid: int, mode: str) -> bool:
        """Set flight mode"""
        conn = self.connections.get(sysid)
        if not conn:
            return False

        mode_mapping = {
            "STABILIZE": 0,
            "GUIDED": 4,
            "AUTO": 3,
            "LOITER": 5,
            "RTL": 6,
            "LAND": 9
        }

        mode_id = mode_mapping.get(mode.upper())
        if mode_id is None:
            return False

        loop = asyncio.get_event_loop()

        def send_mode():
            conn.set_mode(mode_id)

        await loop.run_in_executor(None, send_mode)
        return True

    async def set_speed(self, sysid: int, speed_ms: float) -> bool:
        """Set target speed in m/s"""
        conn = self.connections.get(sysid)
        if not conn:
            return False

        loop = asyncio.get_event_loop()

        def send_speed():
            conn.mav.command_long_send(
                sysid,
                conn.target_component,
                mavutil.mavlink.MAV_CMD_DO_CHANGE_SPEED,
                0, 1, speed_ms, -1, 0, 0, 0, 0
            )

        await loop.run_in_executor(None, send_speed)
        return True

    async def upload_mission(self, sysid: int, waypoints: List[Dict]) -> bool:
        """Upload mission waypoints"""
        conn = self.connections.get(sysid)
        if not conn:
            return False

        loop = asyncio.get_event_loop()

        def send_mission():
            # Clear existing mission
            conn.mav.mission_clear_all_send(sysid, conn.target_component)

            # Send mission count
            conn.mav.mission_count_send(sysid, conn.target_component, len(waypoints))

            # Send each waypoint
            for i, wp in enumerate(waypoints):
                conn.mav.mission_item_int_send(
                    sysid,
                    conn.target_component,
                    i,
                    mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT,
                    mavutil.mavlink.MAV_CMD_NAV_WAYPOINT,
                    0, 1, 0, 0, 0, 0,
                    int(wp["lat"] * 1e7),
                    int(wp["lng"] * 1e7),
                    wp.get("alt", 50.0)
                )

        await loop.run_in_executor(None, send_mission)
        return True

    def get_state(self, drone_id: str) -> Optional[DroneState]:
        """Get current drone state"""
        return self.drone_states.get(drone_id)

    async def disconnect_drone(self, sysid: int):
        """Disconnect from drone"""
        if sysid in self.telemetry_tasks:
            self.telemetry_tasks[sysid].cancel()
            del self.telemetry_tasks[sysid]

        if sysid in self.connections:
            self.connections[sysid].close()
            del self.connections[sysid]


# Global instance
drone_manager = MAVLinkDroneManager()
