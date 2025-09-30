"""
Logging Configuration for WMS Application
Configures file-based logging with rotation
"""
import os
import logging
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from datetime import datetime
import logging
import sys



def setup_logging(app):
    """
    Setup comprehensive logging for the WMS application
    """
    # Logging configuration (equivalent to .env settings)
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO').upper()
    LOG_PATH = os.environ.get('LOG_PATH', '/tmp/wms_logs')
    LOG_FILE_PREFIX = os.environ.get('LOG_FILE_PREFIX', 'wms')
    LOG_MAX_SIZE = int(os.environ.get('LOG_MAX_SIZE', '10485760'))  # 10MB
    LOG_BACKUP_COUNT = int(os.environ.get('LOG_BACKUP_COUNT', '5'))
    LOG_FORMAT = os.environ.get('LOG_FORMAT', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    LOG_TO_CONSOLE = os.environ.get('LOG_TO_CONSOLE', 'True').lower() == 'true'
    LOG_TO_FILE = os.environ.get('LOG_TO_FILE', 'True').lower() == 'true'

    # Create logs directory if it doesn't exist
    os.makedirs(LOG_PATH, exist_ok=True)
    # Configure UTF-8 encoding for better Unicode support
    # Get log level
    log_level = getattr(logging, LOG_LEVEL, logging.INFO)
    
    # Clear any existing handlers
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    
    # Create formatter
    formatter = logging.Formatter(LOG_FORMAT)
    
    # Setup root logger
    logging.root.setLevel(log_level)
    
    handlers = []
    
    # Console handler
    if LOG_TO_CONSOLE:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)
        handlers.append(console_handler)
    
    # File handler with size-based rotation to avoid file locking issues
    if LOG_TO_FILE:
        # Use RotatingFileHandler instead of TimedRotatingFileHandler to avoid Windows file locking issues
        log_file = os.path.join(LOG_PATH, f'{LOG_FILE_PREFIX}.log')
        
        # Try to use the log file, but fall back gracefully if there are permission issues
        try:
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=LOG_MAX_SIZE,
                backupCount=LOG_BACKUP_COUNT,
                encoding='utf-8'
            )
            file_handler.setLevel(log_level)
            file_handler.setFormatter(formatter)
            handlers.append(file_handler)
            
        except (OSError, PermissionError) as e:
            # If we can't write to the main log file, fall back to console only
            print(f"Warning: Could not set up file logging due to permission error: {e}. Using console logging only.")
            if not LOG_TO_CONSOLE:
                # Ensure console logging is enabled if file logging fails
                console_handler = logging.StreamHandler()
                console_handler.setLevel(log_level)
                console_handler.setFormatter(formatter)
                handlers.append(console_handler)
        
        # Error log file with size-based rotation
        error_log_file = os.path.join(LOG_PATH, f'{LOG_FILE_PREFIX}_error.log')
        try:
            error_handler = RotatingFileHandler(
                error_log_file,
                maxBytes=LOG_MAX_SIZE,
                backupCount=LOG_BACKUP_COUNT,
                encoding='utf-8'
            )
            error_handler.setLevel(logging.ERROR)
            error_handler.setFormatter(formatter)
            handlers.append(error_handler)
            
        except (OSError, PermissionError) as e:
            # Error file logging failed, but we'll continue with other handlers
            print(f"Warning: Could not set up error file logging: {e}")
    
    # Add all handlers
    for handler in handlers:
        logging.root.addHandler(handler)
    
    # Setup Flask app logger
    if app:
        app.logger.setLevel(log_level)
        for handler in handlers:
            app.logger.addHandler(handler)
    
    # Log startup message
    logging.info(f"Logging initialized - Level: {LOG_LEVEL}, Path: {LOG_PATH}")
    if LOG_TO_FILE:
        logging.info(f"Size-based rotating log files: {LOG_PATH}/{LOG_FILE_PREFIX}.log and {LOG_PATH}/{LOG_FILE_PREFIX}_error.log (rotates when reaching {LOG_MAX_SIZE} bytes)")
    
    return logging.getLogger(__name__)

def get_log_files_info():
    """
    Get information about current log files
    """
    LOG_PATH = os.environ.get('LOG_PATH', '/tmp/wms_logs')
    LOG_FILE_PREFIX = os.environ.get('LOG_FILE_PREFIX', 'wms')
    
    log_files = []
    if os.path.exists(LOG_PATH):
        for file in os.listdir(LOG_PATH):
            if file.startswith(LOG_FILE_PREFIX):
                file_path = os.path.join(LOG_PATH, file)
                stat = os.stat(file_path)
                log_files.append({
                    'name': file,
                    'path': file_path,
                    'size': stat.st_size,
                    'modified': datetime.fromtimestamp(stat.st_mtime)
                })
    
    return log_files