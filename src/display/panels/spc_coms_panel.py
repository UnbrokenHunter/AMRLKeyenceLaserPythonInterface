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
                CommandComment("1", "Success"),
                CommandComment("0", "Failure"),
                CommandComment(
                    r"TRACKING\s+\S+\s+COUNT=\d+\s+VALUES=.*",
                    "Tracking registry sample list",
                    regex=True,
                ),
                CommandComment(
                    r"TRACKING_AVG\s+\S+\s+[+-]?\d+(?:\.\d+)?",
                    "Tracking registry average",
                    regex=True,
                ),
                CommandComment(
                    r"TRACKING_MAX\s+\S+\s+[+-]?\d+(?:\.\d+)?",
                    "Tracking registry maximum",
                    regex=True,
                ),
                CommandComment(
                    r"TRACKING_MIN\s+\S+\s+[+-]?\d+(?:\.\d+)?",
                    "Tracking registry minimum",
                    regex=True,
                ),
                CommandComment(
                    r"NO_TRACKING_DATA\s+\S+",
                    "Tracking registry has no samples",
                    regex=True,
                ),
                CommandComment(
                    r"PR,\d+",
                    "Keyence active program response",
                    regex=True,
                ),
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
                    spc_command_pattern("GET_PROGRAM"),
                    "Request active Keyence program number",
                    regex=True,
                ),
                CommandComment(
                    spc_command_pattern("PROGRAM?"),
                    "Request active Keyence program number",
                    regex=True,
                ),
                CommandComment(
                    spc_command_pattern("GET_KEYENCE_PROGRAM"),
                    "Request active Keyence program number",
                    regex=True,
                ),
                CommandComment(
                    spc_command_pattern("SET_PROGRAM"),
                    "Change active Keyence program number",
                    regex=True,
                ),
                CommandComment(
                    spc_command_pattern("CHANGE_PROGRAM"),
                    "Change active Keyence program number",
                    regex=True,
                ),
                CommandComment(
                    spc_command_pattern("SET_KEYENCE_PROGRAM"),
                    "Change active Keyence program number",
                    regex=True,
                ),
                CommandComment(
                    spc_command_pattern("START_STREAM"),
                    "Request Keyence streaming output start",
                    regex=True,
                ),
                CommandComment(
                    spc_command_pattern("STOP_STREAM"),
                    "Request Keyence streaming output stop",
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
                    spc_command_pattern("PAUSE_TRACKING"),
                    "Pause collection for a tracking registry while keeping the session open",
                    regex=True,
                ),
                CommandComment(
                    spc_command_pattern("RESUME_TRACKING"),
                    "Resume collection for a paused tracking registry",
                    regex=True,
                ),
                CommandComment(
                    spc_command_pattern("CLEAR_TRACKING"),
                    "Stop and clear samples from a named tracking registry",
                    regex=True,
                ),
                CommandComment(
                    spc_command_pattern("SET_SCAN_METADATA"),
                    "Store optional scan metadata for a tracking registry",
                    regex=True,
                ),
                CommandComment(
                    spc_command_pattern("SET_SCAN_INFO"),
                    "Alias for SET_SCAN_METADATA",
                    regex=True,
                ),
                CommandComment(
                    spc_command_pattern("SCAN_METADATA"),
                    "Alias for SET_SCAN_METADATA",
                    regex=True,
                ),
                CommandComment(
                    spc_command_pattern("NEXT_LAYER"),
                    "Advance a tracking registry to a new scan layer",
                    regex=True,
                ),
                CommandComment(
                    spc_command_pattern("NEXT_SCAN_LAYER"),
                    "Advance a tracking registry to a new scan layer",
                    regex=True,
                ),
                CommandComment(
                    spc_command_pattern("PREPARE"),
                    "Stop scan/tracking, clear registry, then start tracking and stream",
                    regex=True,
                ),
                CommandComment(
                    spc_command_pattern("PREPARE_TRACKING"),
                    "Stop scan/tracking, clear registry, then start tracking and stream",
                    regex=True,
                ),
                CommandComment(
                    spc_command_pattern("PREPARE_SCAN"),
                    "Stop scan/tracking, clear registry, then start tracking and stream",
                    regex=True,
                ),
                CommandComment(
                    spc_command_pattern("SAVE"),
                    "Stop tracking, stop Keyence stream, and export CSV",
                    regex=True,
                ),
                CommandComment(
                    spc_command_pattern("SAVE_TRACKING"),
                    "Stop tracking, stop Keyence stream, and export CSV",
                    regex=True,
                ),
                CommandComment(
                    spc_command_pattern("SAVE_SCAN"),
                    "Stop tracking, stop Keyence stream, and export CSV",
                    regex=True,
                ),
                CommandComment(
                    spc_command_pattern("SAVE_CSV"),
                    "Save a tracking registry to CSV",
                    regex=True,
                ),
                CommandComment(
                    spc_command_pattern("EXPORT_CSV"),
                    "Save a tracking registry to CSV",
                    regex=True,
                ),
                CommandComment(
                    spc_command_pattern("SAVE_TRACKING_CSV"),
                    "Save a tracking registry to CSV",
                    regex=True,
                ),
                CommandComment(
                    spc_command_pattern("EXPORT_TRACKING_CSV"),
                    "Save a tracking registry to CSV",
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
