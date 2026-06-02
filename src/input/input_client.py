"""
Shared abstract input-client interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class InputReading:
    value_mm: float
    result_info: int  # 0 normal, 1 invalid, 2 judgment standby, 3 +range, 4 -range
    judgment: str     # HI, GO, LO, or --
    raw: str

    @property
    def ok(self) -> bool:
        return self.result_info == 0


class InputClient(ABC):
    """Abstract base class for Keyence input devices."""

    @abstractmethod
    def open(self) -> None:
        pass

    @abstractmethod
    def close(self) -> None:
        pass

    @abstractmethod
    def send_command(self, command: str) -> str:
        """Send a device command without the trailing CR. Return response without CR."""
        pass

    @abstractmethod
    def read_once(self) -> InputReading:
        """Read one measurement from the input device."""
        pass

