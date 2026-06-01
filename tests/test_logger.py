"""
Unit Tests for Logger Module
Tests untuk core/logger.py
"""

import pytest
import sys
import os
import tempfile
import shutil
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestLogger:
    """Test suite for SortingLogger"""
    
    @pytest.fixture
    def temp_log_dir(self):
        """Create temporary log directory"""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def logger(self, temp_log_dir, monkeypatch):
        """Create logger with temp directory"""
        # Patch LOG_DIR before importing
        from core import logger as logger_module
        monkeypatch.setattr(logger_module.LogConfig, 'LOG_DIR', temp_log_dir)
        
        # Force new instance
        logger_module._logger_instance = None
        logger_module.SortingLogger._instance = None
        
        log = logger_module.get_logger()
        yield log
        
        # Cleanup
        logger_module._logger_instance = None
        logger_module.SortingLogger._instance = None
    
    # =========================================================================
    # Initialization Tests
    # =========================================================================
    
    def test_logger_singleton(self, temp_log_dir, monkeypatch):
        """Test logger is singleton"""
        from core import logger as logger_module
        monkeypatch.setattr(logger_module.LogConfig, 'LOG_DIR', temp_log_dir)
        
        logger_module._logger_instance = None
        logger_module.SortingLogger._instance = None
        
        log1 = logger_module.get_logger()
        log2 = logger_module.get_logger()
        
        assert log1 is log2
    
    def test_logger_creates_log_directory(self, temp_log_dir, monkeypatch):
        """Test logger creates log directory if not exists"""
        from core import logger as logger_module
        
        new_log_dir = temp_log_dir / "new_logs"
        monkeypatch.setattr(logger_module.LogConfig, 'LOG_DIR', new_log_dir)
        
        logger_module._logger_instance = None
        logger_module.SortingLogger._instance = None
        
        logger_module.get_logger()
        
        assert new_log_dir.exists()
    
    def test_logger_creates_log_files(self, logger, temp_log_dir):
        """Test logger creates expected log files"""
        logger.info("Test message")
        
        expected_files = ['main.log', 'operation.log', 'hardware.log', 'error.log', 'audit.log']
        
        for filename in expected_files:
            assert (temp_log_dir / filename).exists(), f"Missing {filename}"
    
    # =========================================================================
    # Basic Logging Tests
    # =========================================================================
    
    def test_info_logging(self, logger, temp_log_dir):
        """Test INFO level logging"""
        logger.info("Test info message", key="value")
        
        log_content = (temp_log_dir / 'main.log').read_text()
        assert "Test info message" in log_content
        assert "key=value" in log_content
    
    def test_warning_logging(self, logger, temp_log_dir):
        """Test WARNING level logging"""
        logger.warning("Test warning", reason="test")
        
        log_content = (temp_log_dir / 'main.log').read_text()
        assert "WARNING" in log_content
        assert "Test warning" in log_content
    
    def test_error_logging(self, logger, temp_log_dir):
        """Test ERROR level logging"""
        logger.error("Test error", context="unit_test")
        
        log_content = (temp_log_dir / 'error.log').read_text()
        assert "ERROR" in log_content
        assert "Test error" in log_content
    
    def test_error_with_exception(self, logger, temp_log_dir):
        """Test ERROR logging with exception"""
        try:
            raise ValueError("Test exception")
        except Exception as e:
            logger.error("Exception occurred", exception=e)
        
        log_content = (temp_log_dir / 'error.log').read_text()
        assert "Exception occurred" in log_content
    
    # =========================================================================
    # Specialized Logging Tests
    # =========================================================================
    
    def test_operation_logging(self, logger, temp_log_dir):
        """Test operation logging"""
        logger.operation("Package measured", 
            package_id="PKG_001",
            service_type="EXPRESS",
            weight=850)
        
        log_content = (temp_log_dir / 'operation.log').read_text()
        assert "Package measured" in log_content
        assert "PKG_001" in log_content
        assert "EXPRESS" in log_content
    
    def test_hardware_logging(self, logger, temp_log_dir):
        """Test hardware logging"""
        logger.hardware("HX711", "reading", raw_value=12345)
        
        log_content = (temp_log_dir / 'hardware.log').read_text()
        assert "HX711" in log_content
        assert "reading" in log_content
    
    def test_audit_logging(self, logger, temp_log_dir):
        """Test audit logging"""
        logger.audit("package_measured", user="operator_1")
        
        log_content = (temp_log_dir / 'audit.log').read_text()
        assert "package_measured" in log_content
        assert "operator_1" in log_content
    
    # =========================================================================
    # Log Retrieval Tests
    # =========================================================================
    
    def test_get_log_files(self, logger, temp_log_dir):
        """Test get_log_files returns correct paths"""
        log_files = logger.get_log_files()
        
        assert 'main' in log_files
        assert 'operation' in log_files
        assert 'hardware' in log_files
        assert 'error' in log_files
        assert 'audit' in log_files
    
    def test_get_recent_logs(self, logger, temp_log_dir):
        """Test get_recent_logs returns log lines"""
        logger.info("Log line 1")
        logger.info("Log line 2")
        logger.info("Log line 3")
        
        # Need to modify to use temp_log_dir
        from core import logger as logger_module
        logger_module.LogConfig.LOG_DIR = temp_log_dir
        
        lines = logger.get_recent_logs('main', lines=10)
        
        # Should have at least 3 lines
        assert len(lines) >= 3
    
    # =========================================================================
    # Data Formatting Tests
    # =========================================================================
    
    def test_log_format_contains_timestamp(self, logger, temp_log_dir):
        """Test log entries contain timestamp"""
        logger.info("Test message")
        
        log_content = (temp_log_dir / 'main.log').read_text()
        # Format: YYYY-MM-DD HH:MM:SS
        import re
        assert re.search(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}', log_content)
    
    def test_log_format_contains_level(self, logger, temp_log_dir):
        """Test log entries contain level"""
        logger.warning("Test warning")
        
        log_content = (temp_log_dir / 'main.log').read_text()
        assert "WARNING" in log_content


class TestLogConfig:
    """Test LogConfig settings"""
    
    def test_default_log_level(self):
        """Test default log level is INFO"""
        from core.logger import LogConfig
        import logging
        
        assert LogConfig.DEFAULT_LEVEL == logging.INFO
    
    def test_max_bytes_reasonable(self):
        """Test max bytes is reasonable size"""
        from core.logger import LogConfig
        
        # Should be between 1MB and 100MB
        assert 1_000_000 <= LogConfig.MAX_BYTES <= 100_000_000
    
    def test_backup_count_reasonable(self):
        """Test backup count is reasonable"""
        from core.logger import LogConfig
        
        # Should be between 3 and 30
        assert 3 <= LogConfig.BACKUP_COUNT <= 30


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
