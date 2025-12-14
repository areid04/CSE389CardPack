from server_logs.base import Logger
from datetime import datetime

class FileLogger(Logger):
    def __init__(self, path="logs/server.log"):
        self.path = path

    def _write(self, level, msg, data):
        ts = datetime.utcnow().isoformat()
        with open(self.path, "a") as f:
            f.write(f"[{ts}] {level} {msg} {data}\n")

    def info(self, msg, **data):
        self._write("INFO", msg, data)

    def debug(self, msg, **data):
        self._write("DEBUG", msg, data)

    def warning(self, msg, **data):
        self._write("WARN", msg, data)

    def error(self, msg, **data):
        self._write("ERROR", msg, data)
