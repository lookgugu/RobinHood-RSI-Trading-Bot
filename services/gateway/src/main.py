"""
Gateway Service - Authentication and API routing for trading bot.

This service handles:
- Robinhood authentication
- Session management
- Health checks
- Request routing to other services
"""

import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import redis.asyncio as redis

from .auth import RobinhoodAuth, AuthState
from shared.utils.logging import setup_logging

# Setup logging
logger = setup_logging("gateway", level="INFO", format_type="console")


class Settings(BaseModel):
    """Gateway service settings."""

    service_name: str = "gateway"
    redis_url: str = "redis://redis:6379"
    robinhood_username: str = ""
    robinhood_password: str = ""

    class Config:
        env_file = ".env"


settings = Settings()

# Global auth instance
auth_manager: Optional[RobinhoodAuth] = None
redis_client: Optional[redis.Redis] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    global auth_manager, redis_client

    logger.info("Starting Gateway Service...")

    # Initialize Redis connection
    redis_client = redis.from_url(settings.redis_url, decode_responses=True)

    # Initialize auth manager
    auth_manager = RobinhoodAuth(
        username=settings.robinhood_username,
        password=settings.robinhood_password,
        redis_client=redis_client,
    )

    logger.info("Gateway Service started successfully")

    yield

    # Cleanup
    if redis_client:
        await redis_client.close()
    logger.info("Gateway Service stopped")


app = FastAPI(
    title="Trading Bot Gateway",
    description="Authentication and routing service for trading bot",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request/Response models
class LoginRequest(BaseModel):
    """Login request model."""

    username: Optional[str] = None
    password: Optional[str] = None
    mfa_code: Optional[str] = None


class LoginResponse(BaseModel):
    """Login response model."""

    success: bool
    message: str
    requires_mfa: bool = False


class AuthStatusResponse(BaseModel):
    """Auth status response model."""

    authenticated: bool
    username: Optional[str] = None
    session_valid: bool = False


class HealthResponse(BaseModel):
    """Health check response model."""

    status: str
    service: str
    redis_connected: bool
    authenticated: bool


# Dependency to get auth manager
async def get_auth() -> RobinhoodAuth:
    """Get auth manager dependency."""
    if auth_manager is None:
        raise HTTPException(status_code=500, detail="Auth manager not initialized")
    return auth_manager


# Health check endpoint
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Check service health."""
    redis_ok = False
    authenticated = False

    try:
        if redis_client:
            await redis_client.ping()
            redis_ok = True
    except Exception:
        pass

    if auth_manager:
        authenticated = auth_manager.is_authenticated()

    return HealthResponse(
        status="healthy" if redis_ok else "degraded",
        service="gateway",
        redis_connected=redis_ok,
        authenticated=authenticated,
    )


# Authentication endpoints
@app.post("/auth/login", response_model=LoginResponse)
async def login(
    request: LoginRequest,
    auth: RobinhoodAuth = Depends(get_auth),
):
    """Login to Robinhood."""
    try:
        # Use provided credentials or fall back to env vars
        username = request.username or settings.robinhood_username
        password = request.password or settings.robinhood_password

        if not username or not password:
            raise HTTPException(
                status_code=400,
                detail="Username and password required",
            )

        result = await auth.login(username, password, request.mfa_code)

        if result.state == AuthState.AUTHENTICATED:
            return LoginResponse(
                success=True,
                message="Successfully authenticated",
                requires_mfa=False,
            )
        elif result.state == AuthState.MFA_REQUIRED:
            return LoginResponse(
                success=False,
                message="MFA code required",
                requires_mfa=True,
            )
        else:
            return LoginResponse(
                success=False,
                message=result.error or "Authentication failed",
                requires_mfa=False,
            )

    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/auth/logout")
async def logout(auth: RobinhoodAuth = Depends(get_auth)):
    """Logout from Robinhood."""
    try:
        await auth.logout()
        return {"success": True, "message": "Logged out successfully"}
    except Exception as e:
        logger.error(f"Logout error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/auth/status", response_model=AuthStatusResponse)
async def auth_status(auth: RobinhoodAuth = Depends(get_auth)):
    """Get current authentication status."""
    return AuthStatusResponse(
        authenticated=auth.is_authenticated(),
        username=auth.username if auth.is_authenticated() else None,
        session_valid=auth.is_session_valid(),
    )


@app.post("/auth/refresh")
async def refresh_session(auth: RobinhoodAuth = Depends(get_auth)):
    """Refresh the current session."""
    try:
        success = await auth.refresh_session()
        return {
            "success": success,
            "message": "Session refreshed" if success else "Failed to refresh session",
        }
    except Exception as e:
        logger.error(f"Session refresh error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Proxy endpoint to get Robinhood API client
@app.get("/api/client")
async def get_client_info(auth: RobinhoodAuth = Depends(get_auth)):
    """Get Robinhood client information."""
    if not auth.is_authenticated():
        raise HTTPException(status_code=401, detail="Not authenticated")

    return {
        "authenticated": True,
        "client_ready": auth.client is not None,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
