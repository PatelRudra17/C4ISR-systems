from functools import lru_cache
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # Application
    DEBUG: bool = False
    ENVIRONMENT: str = "production"
    ALLOWED_ORIGINS: str = "http://localhost:3000"

    # PostgreSQL
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "aegis_c4isr"
    POSTGRES_USER: str = "aegis_admin"
    POSTGRES_PASSWORD: str = "changeme"

    # InfluxDB
    INFLUX_URL: str = "http://localhost:8086"
    INFLUX_TOKEN: str = "changeme"
    INFLUX_ORG: str = "aegis_command"
    INFLUX_BUCKET_GPS: str = "gps_telemetry"
    INFLUX_BUCKET_SENSOR: str = "sensor_data"
    INFLUX_BUCKET_THREAT: str = "threat_events"
    INFLUX_BUCKET_CYBER: str = "cyber_events"
    INFLUX_PASSWORD: str = "changeme"

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = "changeme"
    REDIS_TTL_GPS: int = 30
    REDIS_TTL_THREAT: int = 300
    REDIS_TTL_DRONE: int = 10

    # JWT
    JWT_SECRET_KEY: str = "changeme-use-openssl-rand-hex-32"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_EXPIRE_DAYS: int = 7

    # AES Encryption (MUST be 32 chars)
    AES_KEY: str = "changeme_exactly_32_chars_key!!"

    # MFA
    MFA_REQUIRED: bool = True
    MFA_ISSUER: str = "AEGIS_C4ISR"

    # MAVLink
    MAVLINK_HOST: str = "0.0.0.0"
    MAVLINK_PORT: int = 14550
    DRONE_TELEMETRY_RATE: int = 10
    MAX_DRONES: int = 32
    GEOFENCE_DEFAULT_RADIUS: int = 5000

    # AI
    YOLO_MODEL_PATH: str = "/app/models/yolov8n.pt"
    AI_CONFIDENCE_THRESHOLD: float = 0.65
    AI_DEVICE: str = "cpu"

    # Kafka
    KAFKA_BOOTSTRAP: str = "localhost:9092"
    KAFKA_TOPIC_GPS: str = "gps.telemetry"
    KAFKA_TOPIC_THREATS: str = "threat.detected"
    KAFKA_TOPIC_AUDIT: str = "audit.log"
    KAFKA_TOPIC_CYBER: str = "cyber.events"

    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 300
    RATE_LIMIT_AUTH_PER_MINUTE: int = 10
    RATE_LIMIT_API_PER_MINUTE: int = 100

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "/var/log/aegis/app.log"

    @property
    def POSTGRES_URL(self) -> str:
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    @property
    def POSTGRES_SYNC_URL(self) -> str:
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    @property
    def REDIS_URL(self) -> str:
        return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/0"

    @property
    def ALLOWED_ORIGINS_LIST(self) -> List[str]:
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",")]

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()
