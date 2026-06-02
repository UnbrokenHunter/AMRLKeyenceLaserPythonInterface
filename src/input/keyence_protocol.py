from __future__ import annotations

from src.input.input_client import InputReading


def parse_ms3_response(response: str) -> InputReading:
    parts = response.strip().split(",")

    if len(parts) != 4:
        raise ValueError(f"Unexpected MS,3,x response: {response!r}")

    command, value_text, result_info_text, judgment = parts

    if command != "MS":
        raise ValueError(f"Expected MS response, got: {response!r}")

    return parse_value_status(value_text, result_info_text, judgment, raw=response)


def parse_stream_response(response: str) -> InputReading:
    parts = response.strip().split(",")

    if len(parts) != 3:
        raise ValueError(f"Unexpected stream response: {response!r}")

    return parse_value_status(parts[0], parts[1], parts[2], raw=response)


def parse_value_status(
    value_text: str,
    result_info_text: str,
    judgment: str,
    raw: str,
) -> InputReading:
    result_info = int(result_info_text)

    return InputReading(
        value_mm=float(value_text),
        result_info=result_info,
        judgment=judgment,
        raw=raw,
    )
