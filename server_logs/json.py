import json
from datetime import datetime
from server_logs.base import Logger

class JSONLogger(Logger):
    def info(self, msg, **data):
        print(json.dumps({
            "ts": datetime.utcnow().isoformat(),
            "level": "INFO",
            "event": msg,
            "data": data
        }))

    def debug(self, msg, **data):
        self._write("DEBUG", msg, data)

    def warning(self, msg, **data):
        self._write("WARN", msg, data)

    def error(self, msg, **data):
        self._write("ERROR", msg, data)