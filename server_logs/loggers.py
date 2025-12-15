from server_logs.chooseLogType import get_logger
from server_logs.file import FileLogger
import os

env = os.getenv("ENV", "dev")

server_logger = get_logger(mode=env, log_type="server")
auction_logger = get_logger(mode=env, log_type="auction")
marketplace_logger = get_logger(mode=env, log_type="marketplace")

transaction_logger = FileLogger(log_type="transactions")