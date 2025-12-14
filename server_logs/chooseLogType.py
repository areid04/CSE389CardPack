from server_logs.stdout import StdoutLogger
from server_logs.file import FileLogger
from server_logs.json import JSONLogger
from server_logs.composite import CompositeLogger

def get_logger(mode="dev"):
    if mode == "prod":
        return CompositeLogger(
            FileLogger(),
            JSONLogger()
        )
    return StdoutLogger()
