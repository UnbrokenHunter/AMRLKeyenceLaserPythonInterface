"""Program/session log writer.

This logger records bridge events before UI display filters such as RAW, TIME,
RX, or TX are applied. It is intended as a durable operator/debugging record of
serial traffic and system events for a single app run.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path


class ProgramLogger:
    def __init__(
        self,
        *,
        log_dir: str | Path = "logs",
        keep_count: int = 25,
    ) -> None:
        self.log_dir = Path(log_dir)
        self.keep_count = max(1, int(keep_count))
        self.path: Path | None = None

    def start(self) -> None:
        self.log_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        self.path = self.log_dir / f"bridge-{timestamp}.log"
        self.write("SYS", "LOGGER", f"Log started: {self.path}")
        self.prune()

    def set_keep_count(self, keep_count: int) -> None:
        self.keep_count = max(1, int(keep_count))
        self.prune()

    def write(self, direction: str, source: str, message: str) -> None:
        if self.path is None:
            self.start()

        assert self.path is not None

        timestamp = datetime.now().isoformat(timespec="milliseconds")
        clean_message = message.replace("\r", "\\r").replace("\n", "\\n")

        with self.path.open("a", encoding="utf-8") as log_file:
            log_file.write(f"{timestamp}\t{direction}\t{source}\t{clean_message}\n")

    def prune(self) -> None:
        if not self.log_dir.exists():
            return

        logs = sorted(
            self.log_dir.glob("bridge-*.log"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )

        for old_log in logs[self.keep_count :]:
            try:
                old_log.unlink()
            except OSError:
                pass
