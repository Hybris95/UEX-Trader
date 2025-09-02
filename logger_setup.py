import logging
import os
from platformdirs import user_data_dir
from global_variables import app_name, uexlog_log_file


def setup_logger(logging_level):
    log_dir = user_data_dir(app_name, ensure_exists=True)
    log_path = os.path.join(log_dir, uexlog_log_file)
    file_handler = logging.FileHandler(log_path)
    stdout_handler = logging.StreamHandler()
    handlers = [file_handler, stdout_handler]
    logging.basicConfig(
        level=logging_level,
        format='%(asctime)s - %(levelname)s - %(message)s - %(filename)s:%(lineno)d',
        handlers=handlers,
        force=True
    )
