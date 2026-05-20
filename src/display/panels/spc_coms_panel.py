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
                CommandComment("START", "Start the SPC process"),
                CommandComment("STOP", "Stop the SPC process"),
                CommandComment("RESET", "Reset the SPC process state"),
            ],
            *args,
            **kwargs,
        )