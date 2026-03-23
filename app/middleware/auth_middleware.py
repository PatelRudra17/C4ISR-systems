from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from fastapi import status

from app.core.security import decode_token
from app.core.redis_client import session_get

# Paths that don't require authentication
PUBLIC_PATHS = {
    "/api/v1/auth/login",
    "/api/v1/auth/refresh",
    "/api/health",
    "/docs",
    "/redoc",
    "/openapi.json"
}


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware to validate JWT tokens on all routes except public paths
    """

    async def dispatch(self, request: Request, call_next):
        # Skip WebSocket upgrades
        if request.headers.get("upgrade") == "websocket":
            return await call_next(request)

        # Skip public paths
        if request.url.path in PUBLIC_PATHS or request.url.path.startswith("/static"):
            return await call_next(request)

        # Extract token from Authorization header
        auth_header = request.headers.get("Authorization")

        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Missing or invalid authorization header"}
            )

        token = auth_header.split(" ")[1]

        # Decode and validate token
        payload = decode_token(token)

        if not payload or payload.get("type") != "access":
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Invalid or expired token"}
            )

        # Verify session exists in Redis
        user_id = payload.get("sub")
        jti = payload.get("jti")

        session_data = await session_get(f"{user_id}:{jti}")

        if not session_data:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Session not found or expired"}
            )

        # Add user info to request state
        request.state.user_id = user_id
        request.state.role = payload.get("role")
        request.state.callsign = payload.get("callsign")
        request.state.permissions = payload.get("permissions", [])

        return await call_next(request)
