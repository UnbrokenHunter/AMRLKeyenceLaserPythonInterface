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
                CommandComment("GET_LAST_HEIGHT", "Request latest known Keyence height"),
                CommandComment("GET_HEIGHT", "Alias for GET_LAST_HEIGHT"),
                CommandComment("HEIGHT?", "Request latest known Keyence height"),
                CommandComment("NO_HEIGHT", "No valid Keyence height is available yet"),
                CommandComment("READ_HEIGHT", "Request a fresh averaged Keyence read"),
                CommandComment("READ_ONCE", "Alias for READ_HEIGHT"),
                CommandComment("START_STREAM", "Request Keyence automatic transmission start"),
                CommandComment("STOP_STREAM", "Request Keyence automatic transmission stop"),
                CommandComment("START_TRACKING", "Start collecting new height samples into a named registry"),
                CommandComment("STOP_TRACKING", "Stop collecting height samples into a named registry"),
                CommandComment("CLEAR_TRACKING", "Clear samples from a named tracking registry"),
                CommandComment("RETURN_TRACKING", "Return all samples from a named tracking registry"),
                CommandComment("AVERAGE_TRACKING", "Return the average of a tracking registry"),
                CommandComment("AVG_TRACKING", "Alias for AVERAGE_TRACKING"),
                CommandComment("MAX_TRACKING", "Return the maximum of a tracking registry"),
                CommandComment("MIN_TRACKING", "Return the minimum of a tracking registry"),
                CommandComment("OK", "Command completed successfully"),
                CommandComment("RESET", "Reset the SPC process state"),
            ],
            *args,
            **kwargs,
        )
