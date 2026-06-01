"""
Shared state models.

These are plain data objects. They make it easy to pass state between:
- the bridge/controller
- the Textual app
- each UI panel
- later SPC/Keyence workers
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class DeviceViewState:
    connected: bool = False
    port: str = ""
    height_mm: Optional[float] = None
    state: str = "Idle"


@dataclass
class BridgeViewState:
    keyence: DeviceViewState = field(default_factory=DeviceViewState)
    spc: DeviceViewState = field(default_factory=DeviceViewState)

    use_simulator: bool = True
    height_data_visible: bool = False
    streaming: bool = False

    keyence_out_no: int = 1
    keyence_poll_interval_ms: int = 20
    spc_baudrate: int = 9600
    spc_line_ending: str = "CRLF"
    log_keep_count: int = 25

    spc_rx_count: int = 0
    spc_tx_count: int = 0
    keyence_tx_count: int = 0
    keyence_rx_count: int = 0

    last_error: Optional[str] = None
    last_update: datetime = field(default_factory=datetime.now)

