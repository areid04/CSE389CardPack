from server_logs.stdout import StdoutLogger
from server_logs.file import FileLogger
from server_logs.json import JSONLogger
from server_logs.composite import CompositeLogger

def get_logger(mode="dev", log_type="server"):
    if mode == "prod":
        return CompositeLogger(
            FileLogger(log_type=log_type),
            JSONLogger(log_type=log_type)
        )
    return StdoutLogger(log_type=log_type)