"""
Robinhood Authentication Manager.

Handles login, session management, and credential security.
"""

import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional
from dataclasses import dataclass

import redis.asyncio as redis

logger = logging.getLogger(__name__)


class AuthState(Enum):
    """Authentication state."""

    NOT_AUTHENTICATED = "not_authenticated"
    AUTHENTICATING = "authenticating"
    MFA_REQUIRED = "mfa_required"
    AUTHENTICATED = "authenticated"
    ERROR = "error"


@dataclass
class AuthResult:
    """Result of an authentication attempt."""

    state: AuthState
    error: Optional[str] = None


class RobinhoodAuth:
    """
    Manages Robinhood authentication and session state.

    Uses Redis for session caching and supports MFA.
    """

    SESSION_KEY = "robinhood:session"
    SESSION_TTL = 3600  # 1 hour

    def __init__(
        self,
        username: str = "",
        password: str = "",
        redis_client: Optional[redis.Redis] = None,
    ):
        self.username = username
        self._password = password
        self._redis = redis_client
        self._state = AuthState.NOT_AUTHENTICATED
        self._client = None
        self._session_expires: Optional[datetime] = None

    @property
    def client(self):
        """Get the Robinhood API client."""
        return self._client

    def is_authenticated(self) -> bool:
        """Check if currently authenticated."""
        return self._state == AuthState.AUTHENTICATED and self._client is not None

    def is_session_valid(self) -> bool:
        """Check if the session is still valid."""
        if not self.is_authenticated():
            return False
        if self._session_expires is None:
            return False
        return datetime.utcnow() < self._session_expires

    async def login(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None,
        mfa_code: Optional[str] = None,
    ) -> AuthResult:
        """
        Login to Robinhood.

        Args:
            username: Robinhood username (optional, uses stored)
            password: Robinhood password (optional, uses stored)
            mfa_code: MFA code if required

        Returns:
            AuthResult with the current state
        """
        self._state = AuthState.AUTHENTICATING

        # Use provided credentials or stored ones
        user = username or self.username
        pwd = password or self._password

        if not user or not pwd:
            self._state = AuthState.ERROR
            return AuthResult(
                state=AuthState.ERROR,
                error="Username and password required",
            )

        try:
            # Import pyrh here to avoid issues if not installed
            from pyrh import Robinhood

            self._client = Robinhood()

            # Attempt login
            if mfa_code:
                self._client.login(username=user, password=pwd, mfa_code=mfa_code)
            else:
                try:
                    self._client.login(username=user, password=pwd)
                except Exception as e:
                    error_str = str(e).lower()
                    if "mfa" in error_str or "two-factor" in error_str:
                        self._state = AuthState.MFA_REQUIRED
                        return AuthResult(state=AuthState.MFA_REQUIRED)
                    raise

            # Successfully authenticated
            self._state = AuthState.AUTHENTICATED
            self._session_expires = datetime.utcnow() + timedelta(seconds=self.SESSION_TTL)
            self.username = user

            # Cache session in Redis
            await self._cache_session()

            logger.info(f"Successfully authenticated as {user}")
            return AuthResult(state=AuthState.AUTHENTICATED)

        except Exception as e:
            self._state = AuthState.ERROR
            self._client = None
            logger.error(f"Authentication failed: {e}")
            return AuthResult(state=AuthState.ERROR, error=str(e))

    async def logout(self) -> None:
        """Logout and clear session."""
        if self._client:
            try:
                self._client.logout()
            except Exception as e:
                logger.warning(f"Error during logout: {e}")

        self._client = None
        self._state = AuthState.NOT_AUTHENTICATED
        self._session_expires = None

        # Clear cached session
        if self._redis:
            try:
                await self._redis.delete(self.SESSION_KEY)
            except Exception as e:
                logger.warning(f"Error clearing session cache: {e}")

        logger.info("Logged out successfully")

    async def refresh_session(self) -> bool:
        """
        Refresh the current session.

        Returns:
            True if session was refreshed successfully
        """
        if not self.is_authenticated():
            return False

        try:
            # Extend session expiry
            self._session_expires = datetime.utcnow() + timedelta(seconds=self.SESSION_TTL)
            await self._cache_session()
            logger.info("Session refreshed")
            return True
        except Exception as e:
            logger.error(f"Failed to refresh session: {e}")
            return False

    async def _cache_session(self) -> None:
        """Cache session information in Redis."""
        if not self._redis:
            return

        try:
            session_data = {
                "username": self.username,
                "authenticated": str(self.is_authenticated()),
                "expires": self._session_expires.isoformat() if self._session_expires else "",
            }
            await self._redis.hset(self.SESSION_KEY, mapping=session_data)
            await self._redis.expire(self.SESSION_KEY, self.SESSION_TTL)
        except Exception as e:
            logger.warning(f"Failed to cache session: {e}")

    async def restore_session(self) -> bool:
        """
        Attempt to restore session from cache.

        Returns:
            True if session was restored
        """
        if not self._redis:
            return False

        try:
            session_data = await self._redis.hgetall(self.SESSION_KEY)
            if not session_data:
                return False

            if session_data.get("authenticated") == "True":
                expires_str = session_data.get("expires", "")
                if expires_str:
                    expires = datetime.fromisoformat(expires_str)
                    if expires > datetime.utcnow():
                        # Session still valid, need to re-authenticate
                        # (actual session tokens can't be cached for security)
                        logger.info("Found cached session, re-authentication required")
                        return False

            return False
        except Exception as e:
            logger.warning(f"Failed to restore session: {e}")
            return False

    def get_client_for_service(self):
        """
        Get the Robinhood client for use by other services.

        Returns:
            The authenticated Robinhood client or None
        """
        if self.is_authenticated():
            return self._client
        return None
