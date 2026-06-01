"""
Logging Module for Sorting System
Hybrid logging with local rotating files.
"""

import sys
import json
import logging
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from typing import Dict, Any, Optional
from pathlib import Path


# =============================================================================
# Configuration
# =============================================================================

class LogConfig:
    """Logging configuration"""
    
    # Log directory
    LOG_DIR = Path(__file__).parent.parent / "logs"
    
    # File settings
    MAX_BYTES = 10 * 1024 * 1024  # 10 MB per file
    BACKUP_COUNT = 7  # Keep 7 rotated files
    
    # Levels
    DEFAULT_LEVEL = logging.INFO
    CONSOLE_LEVEL = logging.INFO
    FILE_LEVEL = logging.DEBUG
    
    # Format
    LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)-12s | %(message)s"
    DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
    
    # Categories
    CATEGORIES = ['main', 'operation', 'hardware', 'error', 'audit', 'performance']


# =============================================================================
# Custom Formatters
# =============================================================================

class JsonFormatter(logging.Formatter):
    """JSON formatter for structured logging"""
    
    def format(self, record):
        log_data = {
            'timestamp': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        # Add extra fields if present
        if hasattr(record, 'extra_data'):
            log_data['data'] = record.extra_data
        
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_data, ensure_ascii=False)


class ColoredFormatter(logging.Formatter):
    """Colored console output for development"""
    
    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
        'RESET': '\033[0m'
    }
    
    def format(self, record):
        color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        reset = self.COLORS['RESET']
        
        record.levelname = f"{color}{record.levelname}{reset}"
        return super().format(record)


# =============================================================================
# Main Logger Class
# =============================================================================

class SortingLogger:
    """
    Central logging handler for sorting system
    
    Features:
    - Multiple log files (main, error, hardware)
    - Rotating file handlers
    - Console output with colors
    - Structured logging with extra data
    
    Usage:
        from core.logger import get_logger
        log = get_logger()
        
        log.operation("Package measured", package_id="PKG_001", weight=850)
        log.hardware("HX711", "reading", raw_value=12345)
        log.error("Measurement failed", exception=e)
    """
    
    _instance = None
    
    def __new__(cls):
        """Singleton pattern"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._setup_log_directory()
        self._setup_loggers()
        self._initialized = True
        
        print("[Logger] Initialized")
    
    def _setup_log_directory(self):
        """Ensure log directory exists"""
        LogConfig.LOG_DIR.mkdir(parents=True, exist_ok=True)
    
    def _setup_loggers(self):
        """Setup all loggers"""
        
        # Main logger
        self.main_logger = self._create_logger(
            'main',
            LogConfig.LOG_DIR / 'main.log'
        )
        
        # Operation logger (package measurements)
        self.operation_logger = self._create_logger(
            'operation',
            LogConfig.LOG_DIR / 'operation.log'
        )
        
        # Hardware logger
        self.hardware_logger = self._create_logger(
            'hardware',
            LogConfig.LOG_DIR / 'hardware.log',
            level=logging.DEBUG
        )
        
        # Error logger
        self.error_logger = self._create_logger(
            'error',
            LogConfig.LOG_DIR / 'error.log',
            level=logging.ERROR
        )
        
        # Audit logger
        self.audit_logger = self._create_logger(
            'audit',
            LogConfig.LOG_DIR / 'audit.log'
        )
    
    def _create_logger(self, name: str, log_file: Path, level=None) -> logging.Logger:
        """Create a configured logger"""
        
        logger = logging.getLogger(f'sorting.{name}')
        logger.setLevel(level or LogConfig.DEFAULT_LEVEL)
        logger.handlers = []  # Clear existing handlers
        
        # File handler with rotation
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=LogConfig.MAX_BYTES,
            backupCount=LogConfig.BACKUP_COUNT,
            encoding='utf-8'
        )
        file_handler.setLevel(LogConfig.FILE_LEVEL)
        file_handler.setFormatter(logging.Formatter(
            LogConfig.LOG_FORMAT,
            LogConfig.DATE_FORMAT
        ))
        logger.addHandler(file_handler)
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(LogConfig.CONSOLE_LEVEL)
        
        # Use colored formatter if terminal supports it
        if sys.stdout.isatty():
            console_handler.setFormatter(ColoredFormatter(
                LogConfig.LOG_FORMAT,
                LogConfig.DATE_FORMAT
            ))
        else:
            console_handler.setFormatter(logging.Formatter(
                LogConfig.LOG_FORMAT,
                LogConfig.DATE_FORMAT
            ))
        
        logger.addHandler(console_handler)
        
        return logger
    
    # =========================================================================
    # Public Logging Methods
    # =========================================================================
    
    def info(self, message: str, **data):
        """General info logging"""
        self._log(self.main_logger, logging.INFO, message, data)
    
    def debug(self, message: str, **data):
        """Debug logging"""
        self._log(self.main_logger, logging.DEBUG, message, data)
    
    def warning(self, message: str, **data):
        """Warning logging"""
        self._log(self.main_logger, logging.WARNING, message, data)
    
    def error(self, message: str, exception: Optional[Exception] = None, **data):
        """Error logging"""
        self._log(self.error_logger, logging.ERROR, message, data, exception)
    
    def critical(self, message: str, exception: Optional[Exception] = None, **data):
        """Critical logging"""
        self._log(self.error_logger, logging.CRITICAL, message, data, exception)
    
    def operation(self, message: str, **data):
        """
        Log package operation
        
        Args:
            message: Operation description
            **data: Additional data (package_id, service_type, weight, etc.)
        """
        self._log(self.operation_logger, logging.INFO, message, data)
    
    def hardware(self, component: str, status: str, **data):
        """
        Log hardware event
        
        Args:
            component: Hardware component name (HX711, Camera, Servo, etc.)
            status: Status or action description
            **data: Additional data (raw_value, calibrated, etc.)
        """
        message = f"{component} | {status}"
        self._log(self.hardware_logger, logging.DEBUG, message, data)
    
    def hardware_warning(self, component: str, issue: str, **data):
        """Log hardware warning"""
        message = f"{component} | {issue}"
        self._log(self.hardware_logger, logging.WARNING, message, data)
    
    def hardware_error(self, component: str, error: str, exception: Optional[Exception] = None, **data):
        """Log hardware error"""
        message = f"{component} | {error}"
        self._log(self.hardware_logger, logging.ERROR, message, data, exception)
        self._log(self.error_logger, logging.ERROR, f"Hardware: {message}", data, exception)
    
    def audit(self, action: str, user: Optional[str] = None, **data):
        """
        Log audit event
        
        Args:
            action: Action performed
            user: User identifier (optional)
            **data: Additional context
        """
        if user:
            data['user'] = user
        self._log(self.audit_logger, logging.INFO, action, data)
    
    # =========================================================================
    # Internal Methods
    # =========================================================================
    
    def _log(self, logger: logging.Logger, level: int, message: str, 
             data: Dict[str, Any], exception: Optional[Exception] = None):
        """Internal log method"""
        
        # Format message with data
        if data:
            data_str = ' | '.join(f"{k}={v}" for k, v in data.items())
            full_message = f"{message} | {data_str}"
        else:
            full_message = message
        
        # Create log record with extra data
        record = logger.makeRecord(
            logger.name,
            level,
            "(unknown)",
            0,
            full_message,
            None,
            None
        )
        record.extra_data = data
        
        # Log with or without exception
        if exception:
            logger.log(level, full_message, exc_info=exception)
        else:
            logger.handle(record)
    
    def get_log_files(self) -> Dict[str, Path]:
        """Get paths to all log files"""
        return {
            'main': LogConfig.LOG_DIR / 'main.log',
            'operation': LogConfig.LOG_DIR / 'operation.log',
            'hardware': LogConfig.LOG_DIR / 'hardware.log',
            'error': LogConfig.LOG_DIR / 'error.log',
            'audit': LogConfig.LOG_DIR / 'audit.log'
        }
    
    def get_recent_logs(self, category: str = 'main', lines: int = 100) -> list:
        """
        Get recent log lines from file
        
        Args:
            category: Log category (main, operation, hardware, error, audit)
            lines: Number of lines to return
        
        Returns:
            List of log lines (newest first)
        """
        log_file = LogConfig.LOG_DIR / f'{category}.log'
        
        if not log_file.exists():
            return []
        
        with open(log_file, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()
        
        return all_lines[-lines:][::-1]  # Return newest first


# =============================================================================
# Module-level Functions
# =============================================================================

_logger_instance = None

def get_logger() -> SortingLogger:
    """
    Get the singleton logger instance
    
    Returns:
        SortingLogger: The shared logger instance
    
    Usage:
        from core.logger import get_logger
        log = get_logger()
        log.info("Hello world")
    """
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = SortingLogger()
    return _logger_instance


def setup_logging():
    """
    Initialize logging system
    
    Returns:
        SortingLogger: Configured logger instance
    """
    return get_logger()


# =============================================================================
# Quick Test
# =============================================================================

if __name__ == "__main__":
    # Test logging
    log = get_logger()
    
    log.info("Logger test started")
    log.debug("This is a debug message", test_data=123)
    log.operation("Package measured", package_id="TEST_001", service_type="EXPRESS", weight=850)
    log.hardware("HX711", "reading", raw_value=12345, calibrated=850.5)
    log.warning("Test warning", reason="just testing")
    log.audit("test_action", user="developer")
    
    try:
        raise ValueError("Test exception")
    except Exception as e:
        log.error("Test error occurred", exception=e, context="unit_test")
    
    print("\nLogger test complete!")
    print(f"Log files: {log.get_log_files()}")
