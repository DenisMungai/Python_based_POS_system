"""Small synchronous event bus for backend-to-UI notifications."""

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Event:
    """An immutable event and its structured payload."""

    name: str
    payload: dict[str, Any]


class EventBus:
    """Publish events to registered listeners."""

    def __init__(self) -> None:
        self._listeners: dict[str, list[Callable[[Event], None]]] = defaultdict(list)

    def subscribe(self, event_name: str, listener: Callable[[Event], None]) -> Callable[[], None]:
        """Register a listener and return an unsubscribe function."""
        self._listeners[event_name].append(listener)

        def unsubscribe() -> None:
            listeners = self._listeners.get(event_name, [])
            if listener in listeners:
                listeners.remove(listener)

        return unsubscribe

    def publish(self, event_name: str, **payload: Any) -> None:
        """Publish an event to a stable snapshot of current listeners."""
        event = Event(event_name, payload)
        for listener in tuple(self._listeners.get(event_name, ())):
            listener(event)
