from server_logs.base import Logger
from datetime import datetime
from pathlib import Path
import json

class FileLogger(Logger):
    def __init__(self, log_type="server", base_path="logs"):
        self.log_type = log_type
        self.path = Path(base_path) / f"{log_type}.log"
        
        # Ensure directory exists
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _write(self, level, msg, data):
        ts = datetime.utcnow().isoformat()
        with open(self.path, "a") as f:
            f.write(json.dumps({
                "ts": ts,
                "log_type": self.log_type,
                "level": level,
                "event": msg,
                **data
            }) + "\n")

    def info(self, msg, **data):
        self._write("INFO", msg, data)

    def debug(self, msg, **data):
        self._write("DEBUG", msg, data)

    def warning(self, msg, **data):
        self._write("WARN", msg, data)

    def error(self, msg, **data):
        self._write("ERROR", msg, data)