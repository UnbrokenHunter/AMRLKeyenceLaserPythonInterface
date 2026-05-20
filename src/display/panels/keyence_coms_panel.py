"""Panel that displays Keyence communications."""

from __future__ import annotations

from .common_coms_panel import CommandComment, CommonComsPanel


class KeyenceComsPanel(CommonComsPanel):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(
            title="Keyence Coms",
            id_prefix="keyence",
            default_show_tx=True,
            default_show_rx=False,
            default_raw=True,
            command_comments=[
                CommandComment("R0", "Reset the Keyence controller"),
                CommandComment("MC,1", "Set measurement control mode"),
                CommandComment("LC,1", "Set laser control mode"),
                CommandComment("TS,1,1", "Start timing/sampling operation"),
                CommandComment("TS,0,1", "Stop timing/sampling operation"),
                CommandComment("MS,3,1", "Read measurement data from OUT1"),
                CommandComment("MS,3,2", "Read measurement data from OUT2"),
                CommandComment("NT", "Start continuous automatic transmission"),
            ],
            *args,
            **kwargs,
        )