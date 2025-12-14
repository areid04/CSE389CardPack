from server_logs.base import Logger
from datetime import datetime

class StdoutLogger(Logger):
    def _log(self, level, msg, data):
        ts = datetime.utcnow().isoformat()
        print(f"[{ts}] {level} {msg} {data}")

    def info(self, msg, **data):
        self._log("INFO", msg, data)

    def debug(self, msg, **data):
        self._log("DEBUG", msg, data)

    def warning(self, msg, **data):
        self._log("WARN", msg, data)

    def error(self, msg, **data):
        self._log("ERROR", msg, data)
