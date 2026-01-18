import json
import logging
from typing import Optional
import redis.asyncio as redis

from .events import BaseEvent

logger = logging.getLogger(__name__)


class EventPublisher:
    """Publishes events to Redis pub/sub channels."""

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        self._client: Optional[redis.Redis] = None

    async def connect(self) -> None:
        """Connect to Redis."""
        if self._client is None:
            self._client = redis.from_url(self.redis_url, decode_responses=True)
            logger.info(f"Connected to Redis at {self.redis_url}")

    async def disconnect(self) -> None:
        """Disconnect from Redis."""
        if self._client:
            await self._client.close()
            self._client = None
            logger.info("Disconnected from Redis")

    async def publish(self, event: BaseEvent) -> int:
        """
        Publish an event to its designated channel.

        Args:
            event: The event to publish

        Returns:
            Number of subscribers that received the message
        """
        if self._client is None:
            await self.connect()

        channel = event.to_channel()
        message = event.model_dump_json()

        try:
            subscribers = await self._client.publish(channel, message)
            logger.debug(f"Published {event.event_type} to {channel} ({subscribers} subscribers)")
            return subscribers
        except Exception as e:
            logger.error(f"Failed to publish event: {e}")
            raise

    async def publish_raw(self, channel: str, data: dict) -> int:
        """
        Publish raw data to a specific channel.

        Args:
            channel: The channel name
            data: Dictionary to publish as JSON

        Returns:
            Number of subscribers that received the message
        """
        if self._client is None:
            await self.connect()

        message = json.dumps(data, default=str)

        try:
            subscribers = await self._client.publish(channel, message)
            logger.debug(f"Published to {channel} ({subscribers} subscribers)")
            return subscribers
        except Exception as e:
            logger.error(f"Failed to publish to {channel}: {e}")
            raise

    async def __aenter__(self) -> "EventPublisher":
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.disconnect()
