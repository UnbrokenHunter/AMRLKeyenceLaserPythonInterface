"""
Events emitted by the controller and consumed by the UI.

This keeps the UI from needing to know low-level serial details.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Any


class BridgeEventType(Enum):
    SPC_RECEIVED = auto()
    SPC_SENT = auto()
    KEYENCE_SENT = auto()
    KEYENCE_RECEIVED = auto()
    KEYENCE_STREAM_RECEIVED = auto()
    SYSTEM = auto()
    STATUS_CHANGED = auto()
    ERROR = auto()


@dataclass(frozen=True)
class BridgeEvent:
    type: BridgeEventType
    message: str
    payload: Any = None
