from server_logs.base import Logger
from datetime import datetime
import json

class JSONLogger(Logger):
    def __init__(self, log_type="server"):
        self.log_type = log_type

    def _log(self, level, msg, data):
        print(json.dumps({
            "ts": datetime.utcnow().isoformat(),
            "log_type": self.log_type,
            "level": level,
            "event": msg,
            "data": data
        }))

    def info(self, msg, **data):
        self._log("INFO", msg, data)

    def debug(self, msg, **data):
        self._log("DEBUG", msg, data)

    def warning(self, msg, **data):
        self._