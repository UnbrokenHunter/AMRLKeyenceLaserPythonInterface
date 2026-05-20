import re

from src.display.panels.common_coms_panel import CommonComsPanel, CommandComment


MEASUREMENT_FORMAT_COMMENTS = {
    "0": "value only",
    "1": "value plus status info",
    "2": "value plus HI/GO/LO result",
    "3": "value plus status info and HI/GO/LO result",
    "4": "counter value plus measurement value",
    "5": "counter value, measurement value, and status info",
    "6": "counter value, measurement value, and HI/GO/LO result",
    "7": "counter value, measurement value, status info, and HI/GO/LO result",
}


COMMAND_ERROR_COMMENTS = {
    "72": "The controller did not respond in time",
    "73": "The command was the wrong length",
    "74": "The controller does not recognize this command",
    "81": "The controller is in the wrong mode/state for this command",
    "82": "The command has the wrong number of values after it",
    "83": "One of the values after the command is outside the allowed range",
    "84": "The command is recognized, but it failed for this specific situation",
}


CONTROLLER_ERROR_COMMENTS = {
    "01": "Head 1 is not communicating; check optical unit/cable",
    "02": "Head 2 is not communicating; check optical unit/cable",
    "03": "Head 3 is not communicating; check optical unit/cable",
    "04": "Head 4 is not communicating; check optical unit/cable",
    "05": "Head 5 is not communicating; check optical unit/cable",
    "06": "Head 6 is not communicating; check optical unit/cable",
    "11": "No optical unit/head is detected",
    "13": "Configured head count does not match connected heads",
    "16": "Add-on unit is not communicating",
    "17": "Add-on unit is not communicating",
    "19": "Expansion unit count does not match setup",
    "20": "Duplicate/incompatible expansion unit type",
    "21": "Internal controller hardware error",
    "22": "Internal controller memory error",
    "23": "Internal controller memory error",
    "24": "Internal controller memory error",
    "25": "Internal controller memory error",
    "27": "Controller and optical unit models do not match",
    "31": "General controller fault",
    "32": "General controller fault",
    "33": "General controller fault",
    "35": "General controller fault",
    "36": "Ethernet hardware/communication fault",
    "37": "USB hardware/communication fault",
    "38": "RS-232C hardware/communication fault",
}

RESULT_INFO_COMMENTS = {
    "0": "good/valid reading",
    "1": "invalid reading",
    "2": "reading has a warning",
}


def describe_error_response(match: re.Match[str]) -> str:
    failed_command = match.group(1)
    error_code = match.group(2)

    explanation = COMMAND_ERROR_COMMENTS.get(
        error_code,
        "Unknown command error",
    )

    return f"{failed_command} failed: {explanation} (code {error_code})"


def describe_short_error_response(match: re.Match[str]) -> str:
    error_code = match.group(1)

    explanation = CONTROLLER_ERROR_COMMENTS.get(
        error_code,
        "Unknown controller error",
    )

    return f"Controller status error: {explanation} (ER,{error_code})"


def describe_ms_command(match: re.Match[str]) -> str:
    mode = match.group(1)
    out_no = match.group(2)

    mode_comment = MEASUREMENT_FORMAT_COMMENTS.get(
        mode,
        "unknown output format",
    )

    return f"Read OUT{out_no}; format {mode} means {mode_comment}"


def describe_ms_short_command(match: re.Match[str]) -> str:
    mode = match.group(1)

    mode_comment = MEASUREMENT_FORMAT_COMMENTS.get(
        mode,
        "unknown output format",
    )

    return f"Read measurement; format {mode} means {mode_comment}; OUT was not specified"


def describe_mm_command(match: re.Match[str]) -> str:
    mode = match.group(1)
    out_mask = match.group(2)

    selected_outs = [
        f"OUT{i + 1}"
        for i, bit in enumerate(out_mask)
        if bit == "1"
    ]

    outs_text = ", ".join(selected_outs) if selected_outs else "no OUT channels"

    mode_comment = MEASUREMENT_FORMAT_COMMENTS.get(
        mode,
        "unknown output format",
    )

    return f"Read multiple outputs: {outs_text}; format {mode} means {mode_comment}"


def describe_ma_command(match: re.Match[str]) -> str:
    mode = match.group(1)

    mode_comment = MEASUREMENT_FORMAT_COMMENTS.get(
        mode,
        "unknown output format",
    )

    return f"Read all outputs; format {mode} means {mode_comment}"


def describe_ms_response(match: re.Match[str]) -> str:
    value = match.group(1)
    result_info = match.group(2)
    judgment = match.group(3)

    result_text = RESULT_INFO_COMMENTS.get(
        result_info,
        f"status {result_info}",
    )

    return f"Measurement received: {value}; {result_text}; result is {judgment}"


def describe_avg_response(match: re.Match[str]) -> str:
    value = match.group(1)
    result_info = match.group(2)
    judgment = match.group(3)

    result_text = RESULT_INFO_COMMENTS.get(
        result_info,
        f"status {result_info}",
    )

    return f"Averaged reading: {value}; {result_text}; result is {judgment}"


def describe_ms_invalid_response(match: re.Match[str]) -> str:
    value = match.group(1)
    result_info = match.group(2)
    judgment = match.group(3)

    result_text = RESULT_INFO_COMMENTS.get(
        result_info,
        f"status {result_info}",
    )

    return f"Special/invalid reading received: {value}; {result_text}; result is {judgment}"


def describe_measurement_control(match: re.Match[str]) -> str:
    state = match.group(1)

    if state == "1":
        return "Start measuring"

    return "Stop measuring"


def describe_laser_control(match: re.Match[str]) -> str:
    state = match.group(1)

    if state == "1":
        return "Turn the laser ON"

    return "Turn the laser OFF"


def describe_timing_single(match: re.Match[str]) -> str:
    state = match.group(1)
    out_no = match.group(2)

    state_text = "start/update" if state == "1" else "stop"
    return f"{state_text} timing for OUT{out_no}"


def describe_auto_zero_single(match: re.Match[str]) -> str:
    state = match.group(1)
    out_no = match.group(2)

    state_text = "turn on" if state == "1" else "clear/turn off"
    return f"{state_text} auto-zero for OUT{out_no}"


def describe_reset_single(match: re.Match[str]) -> str:
    state = match.group(1)
    out_no = match.group(2)

    state_text = "start" if state == "1" else "stop"
    return f"{state_text} measurement reset for OUT{out_no}"


def describe_keyence_text(text: str) -> str:
    text = text.strip().upper()

    for item in KEYENCE_COMMAND_COMMENTS:
        if item.regex:
            match = re.fullmatch(item.pattern, text)
            if match is None:
                continue

            if callable(item.comment):
                return item.comment(match)

            return item.comment

        if text == item.pattern.upper():
            if callable(item.comment):
                raise TypeError("Callable command comments require regex=True.")

            return item.comment

    return "Unknown command or response"


def describe_repeated_command(match: re.Match[str]) -> str:
    repeated_message = match.group(1)
    count = match.group(2)

    base_comment = describe_keyence_text(repeated_message)

    return f"{base_comment}; happened {count} times"


KEYENCE_COMMAND_COMMENTS = [
    CommandComment(r"(.+) REPEATED (\d+) TIMES", describe_repeated_command, regex=True),

    CommandComment(r"ER,(\d{2})", describe_short_error_response, regex=True),
    CommandComment(r"ER,([^,]+),(\d{2})", describe_error_response, regex=True),

    CommandComment(
        r"MS,([+-]?\d+(?:\.\d+)?),(\d+),(HI|GO|LO|--)",
        describe_ms_response,
        regex=True,
    ),
    CommandComment(
        r"AVG,([+-]?\d+(?:\.\d+)?),(\d+),(HI|GO|LO|--)",
        describe_avg_response,
        regex=True,
    ),
    CommandComment(
        r"MS,([+-]?F+),(\d+),(HI|GO|LO|--)",
        describe_ms_invalid_response,
        regex=True,
    ),

    CommandComment(r"MS,([0-7]),([1-8])", describe_ms_command, regex=True),
    CommandComment(r"MS,([0-7])", describe_ms_short_command, regex=True),
    CommandComment(r"MM,([0-7]),([01]{8})", describe_mm_command, regex=True),
    CommandComment(r"MA,([0-7])", describe_ma_command, regex=True),

    CommandComment(r"MC,([01])", describe_measurement_control, regex=True),
    CommandComment(r"LC,([01])", describe_laser_control, regex=True),
    CommandComment(r"TS,([01]),([1-8])", describe_timing_single, regex=True),
    CommandComment(r"ZS,([01]),([1-8])", describe_auto_zero_single, regex=True),
    CommandComment(r"RS,([01]),([1-8])", describe_reset_single, regex=True),

    CommandComment("Q0", "Go to setup/settings mode"),
    CommandComment("R0", "Go to normal measurement mode"),

    CommandComment("MS", "Read one measurement output. Use: MS,format,OUT"),
    CommandComment("MM", "Read multiple measurement outputs"),
    CommandComment("MA", "Read all measurement outputs"),

    CommandComment("TS", "Start/stop timing for one output. Use: TS,on/off,OUT"),
    CommandComment("TM", "Start/stop timing for multiple outputs"),
    CommandComment("T1", "Start/stop timing for OUT1"),
    CommandComment("T2", "Start/stop timing for OUT2"),
    CommandComment("TA", "Start/stop timing for OUT1 and OUT2"),

    CommandComment("ZS", "Turn auto-zero on/off for one output. Use: ZS,on/off,OUT"),
    CommandComment("ZM", "Turn auto-zero on/off for multiple outputs"),
    CommandComment("Z1", "Turn auto-zero on/off for OUT1"),
    CommandComment("Z2", "Turn auto-zero on/off for OUT2"),
    CommandComment("ZA", "Turn auto-zero on/off for OUT1 and OUT2"),

    CommandComment("RS", "Reset one measurement value. Use: RS,on/off,OUT"),
    CommandComment("RM", "Reset multiple measurement values"),
    CommandComment("R1", "Reset measurement value for OUT1"),
    CommandComment("R2", "Reset measurement value for OUT2"),
    CommandComment("RA", "Reset measurement value for OUT1 and OUT2"),

    CommandComment("KL", "Lock or unlock the front panel buttons"),

    CommandComment("PW", "Switch to a different saved program"),
    CommandComment("PR", "Read the current program number"),

    CommandComment("MC", "Start or stop measurement"),
    CommandComment("LC", "Turn laser emission on or off"),

    CommandComment("NS", "Start automatic/continuous sending"),
    CommandComment("NT", "Stop automatic/continuous sending"),

    CommandComment("SW,MK", "Set the masked measurement range"),
    CommandComment("SR,MK", "Read the masked measurement range"),

    CommandComment("SW,AH", "Set how invalid readings are handled"),
    CommandComment("SR,AH", "Read how invalid readings are handled"),

    CommandComment("SW,SC", "Set measurement scaling"),
    CommandComment("SR,SC", "Read measurement scaling"),

    CommandComment("SW,OF", "Set measurement offset"),
    CommandComment("SR,OF", "Read measurement offset"),

    CommandComment("SW,LM", "Set tolerance limits"),
    CommandComment("SR,LM", "Read tolerance limits"),

    CommandComment("CC", "Clear the encoder pulse count"),
    CommandComment("CR", "Read the encoder pulse count"),

    CommandComment("DS", "Start saving measurement data"),
    CommandComment("DT", "Stop saving measurement data"),
    CommandComment("DC", "Clear saved measurement data"),
    CommandComment("DA", "Check whether data storage is running"),
]


class KeyenceComsPanel(CommonComsPanel):
    def __init__(self, *args, **kwargs):
        super().__init__(
            *args,
            title="Keyence Coms",
            id_prefix="keyence",
            default_show_tx=True,
            default_show_rx=False,
            default_raw=True,
            command_comments=KEYENCE_COMMAND_COMMENTS,
            **kwargs,
        )