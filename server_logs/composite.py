from server_logs.base import Logger

class CompositeLogger(Logger):
    def __init__(self, *loggers: Logger):
        self.loggers = loggers

    def info(self, msg, **data):
        for l in self.loggers:
            l.info(msg, **data)

    def debug(self, msg, **data):
        for l in self.loggers:
            l.debug(msg, **data)

    def warning(self, msg, **data):
        for l in self.loggers:
            l.warning(msg, **data)

    def error(self, msg, **data):
        for l in self.loggers:
            l.error(msg, **data)
