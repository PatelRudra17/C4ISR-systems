import hashlib
import logging
from datetime import datetime
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.security import compute_audit_hash

logger = logging.getLogger("aegis.audit")


class AuditLoggerMiddleware(BaseHTTPMiddleware):
    """
    Middleware to log all API requests for audit trail
    Creates tamper-evident log entries with SHA-256 hash
    """

    async def dispatch(self, request: Request, call_next):
        # Record start time
        start_time = datetime.utcnow()

        # Process request
        response = await call_next(request)

        # Create audit log entry
        entry = {
            "timestamp": start_time.isoformat(),
            "user_id": getattr(request.state, "user_id", None),
            "callsign": getattr(request.state, "callsign", "ANONYMOUS"),
            "method": request.method,
            "path": request.url.path,
            "query": str(request.url.query),
            "ip_address": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent"),
            "status_code": response.status_code,
        }

        # Compute tamper-evident hash
        entry["hash"] = compute_audit_hash(entry)

        # Log to Python logger (can be configured to write to file/syslog)
        logger.info(
            f"[AUDIT] {entry['callsign']} | {entry['method']} {entry['path']} | "
            f"Status: {entry['status_code']} | IP: {entry['ip_address']} | "
            f"Hash: {entry['hash']}"
        )

        # TODO: Optionally write to PostgreSQL audit_logs table
        # This would require database connection which can be done asynchronously

        return response
