import json
import logging
import asyncio
from typing import Callable, Dict, List, Optional, Any
import redis.asyncio as redis

from .events import EventType

logger = logging.getLogger(__name__)


class EventSubscriber:
    """Subscribes to events from Redis pub/sub channels."""

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        self._client: Optional[redis.Redis] = None
        self._pubsub: Optional[redis.client.PubSub] = None
        self._handlers: Dict[str, List[Callable]] = {}
        self._running = False

    async def connect(self) -> None:
        """Connect to Redis."""
        if self._client is None:
            self._client = redis.from_url(self.redis_url, decode_responses=True)
            self._pubsub = self._client.pubsub()
            logger.info(f"Subscriber connected to Redis at {self.redis_url}")

    async def disconnect(self) -> None:
        """Disconnect from Redis."""
        self._running = False
        if self._pubsub:
            await self._pubsub.unsubscribe()
            await self._pubsub.close()
            self._pubsub = None
        if self._client:
            await self._client.close()
            self._client = None
            logger.info("Subscriber disconnected from Redis")

    def on_event(self, event_type: EventType) -> Callable:
        """
        Decorator to register an event handler.

        Usage:
            @subscriber.on_event(EventType.PRICE_UPDATE)
            async def handle_price(data):
                print(data)
        """
        channel = f"trading:{event_type.value}"

        def decorator(func: Callable) -> Callable:
            if channel not in self._handlers:
                self._handlers[channel] = []
            self._handlers[channel].append(func)
            return func

        return decorator

    def add_handler(self, event_type: EventType, handler: Callable) -> None:
        """Add a handler for an event type."""
        channel = f"trading:{event_type.value}"
        if channel not in self._handlers:
            self._handlers[channel] = []
        self._handlers[channel].append(handler)

    async def subscribe(self, *event_types: EventType) -> None:
        """Subscribe to specific event types."""
        if self._pubsub is None:
            await self.connect()

        channels = [f"trading:{et.value}" for et in event_types]
        await self._pubsub.subscribe(*channels)
        logger.info(f"Subscribed to channels: {channels}")

    async def subscribe_all(self) -> None:
        """Subscribe to all registered handler channels."""
        if self._pubsub is None:
            await self.connect()

        if self._handlers:
            await self._pubsub.subscribe(*self._handlers.keys())
            logger.info(f"Subscribed to channels: {list(self._handlers.keys())}")

    async def _process_message(self, message: Dict[str, Any]) -> None:
        """Process a received message."""
        if message["type"] != "message":
            return

        channel = message["channel"]
        handlers = self._handlers.get(channel, [])

        if not handlers:
            logger.warning(f"No handlers for channel: {channel}")
            return

        try:
            data = json.loads(message["data"])
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse message: {e}")
            return

        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(data)
                else:
                    handler(data)
            except Exception as e:
                logger.error(f"Handler error for {channel}: {e}")

    async def listen(self) -> None:
        """Start listening for messages."""
        if self._pubsub is None:
            await self.connect()

        self._running = True
        logger.info("Starting event listener...")

        while self._running:
            try:
                message = await self._pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=1.0
                )
                if message:
                    await self._process_message(message)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in event listener: {e}")
                await asyncio.sleep(1)

    async def listen_once(self, timeout: float = 5.0) -> Optional[Dict[str, Any]]:
        """Listen for a single message with timeout."""
        if self._pubsub is None:
            await self.connect()

        message = await self._pubsub.get_message(
            ignore_subscribe_messages=True, timeout=timeout
        )

        if message and message["type"] == "message":
            try:
                return json.loads(message["data"])
            except json.JSONDecodeError:
                return None

        return None

    async def __aenter__(self) -> "EventSubscriber":
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.disconnect()
