"""Panel that displays SPC communications."""

from __future__ import annotations

from .common_coms_panel import CommandComment, CommonComsPanel


class SpcComsPanel(CommonComsPanel):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(
            title="SPC Coms",
            id_prefix="spc",
            default_show_tx=True,
            default_show_rx=True,
            default_raw=True,
            command_comments=[
                CommandComment("PING", "Check whether SPC is responding"),
                CommandComment("PONG", "Reply to SPC heartbeat check"),
                CommandComment("STATUS", "Read bridge/Keyence/SPC status"),
                CommandComment("GET_HEIGHT", "Request latest known Keyence height"),
                CommandComment("HEIGHT?", "Request latest known Keyence height"),
                CommandComment("NO_HEIGHT", "No valid Keyence height is available yet"),
                CommandComment("READ_ONCE", "Request a fresh averaged Keyence read"),
                CommandComment("START_STREAM", "Request Keyence automatic transmission start"),
                CommandComment("STOP_STREAM", "Request Keyence automatic transmission stop"),
                CommandComment("OK", "Command completed successfully"),
                CommandComment("RESET", "Reset the SPC process state"),
            ],
            *args,
            **kwargs,
        )
