"""Panel that displays SPC communications."""

from __future__ import annotations

import re

from .common_coms_panel import CommandComment, CommonComsPanel


def spc_command_pattern(name: str) -> str:
    flexible_name = r"[\s_]+".join(re.escape(part) for part in name.split("_"))
    return rf"{flexible_name}(?:\s+.*)?"


class SpcComsPanel(CommonComsPanel):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(
            title="SPC Coms",
            id_prefix="spc",
            default_show_tx=True,
            default_show_rx=True,
            default_raw=True,
            command_comments=[
                CommandComment(
                    spc_command_pattern("PING"),
                    "Check whether the bridge replies with numeric success",
                    regex=True,
                ),
                CommandComment(
                    spc_command_pattern("STATUS"),
                    "Read bridge/Keyence/SPC status",
                    regex=True,
                ),
                CommandComment(
                    spc_command_pattern("GET_LAST_HEIGHT"),
                    "Request latest known Keyence height",
                    regex=True,
                ),
                CommandComment(
                    spc_command_pattern("GET_HEIGHT"),
                    "Alias for GET_LAST_HEIGHT",
                    regex=True,
                ),
                CommandComment(
                    spc_command_pattern("HEIGHT?"),
                    "Request latest known Keyence height",
                    regex=True,
                ),
                CommandComment(
                    spc_command_pattern("NO_HEIGHT"),
                    "No valid Keyence height is available yet",
                    regex=True,
                ),
                CommandComment(
                    spc_command_pattern("READ_HEIGHT"),
                    "Request a fresh averaged Keyence read",
                    regex=True,
                ),
                CommandComment(
                    spc_command_pattern("READ_ONCE"),
                    "Alias for READ_HEIGHT",
                    regex=True,
                ),
                CommandComment(
                    spc_command_pattern("START_STREAM"),
                    "Request Keyence automatic transmission start",
                    regex=True,
                ),
                CommandComment(
                    spc_command_pattern("STOP_STREAM"),
                    "Request Keyence automatic transmission stop",
                    regex=True,
                ),
                CommandComment(
                    spc_command_pattern("START_TRACKING"),
                    "Start collecting new height samples into a named registry",
                    regex=True,
                ),
                CommandComment(
                    spc_command_pattern("STOP_TRACKING"),
                    "Stop collecting height samples into a named registry",
                    regex=True,
                ),
                CommandComment(
                    spc_command_pattern("CLEAR_TRACKING"),
                    "Clear samples from a named tracking registry",
                    regex=True,
                ),
                CommandComment(
                    spc_command_pattern("RETURN_TRACKING"),
                    "Return all samples from a named tracking registry",
                    regex=True,
                ),
                CommandComment(
                    spc_command_pattern("AVERAGE_TRACKING"),
                    "Return the average of a tracking registry",
                    regex=True,
                ),
                CommandComment(
                    spc_command_pattern("AVG_TRACKING"),
                    "Alias for AVERAGE_TRACKING",
                    regex=True,
                ),
                CommandComment(
                    spc_command_pattern("MAX_TRACKING"),
                    "Return the maximum of a tracking registry",
                    regex=True,
                ),
                CommandComment(
                    spc_command_pattern("MIN_TRACKING"),
                    "Return the minimum of a tracking registry",
                    regex=True,
                ),
                CommandComment(
                    spc_command_pattern("RESET"),
                    "Reset the SPC process state",
                    regex=True,
                ),
            ],
            *args,
            **kwargs,
        )
