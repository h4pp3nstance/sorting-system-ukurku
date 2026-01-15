# 📊 Logging Architecture Plan
## Sistem Pengukuran & Penyortiran Paket

---

## 1. Overview

Arsitektur logging dirancang untuk:
- ✅ Operasi offline (network down)
- ✅ Remote access untuk troubleshooting
- ✅ Minimal storage footprint
- ✅ Performance-first design
- ✅ Audit trail compliance

---

## 2. Log Categories

| Category | Purpose | Priority | Storage |
|----------|---------|----------|---------|
| **OPERATION** | Package measurements, sorting | HIGH | Firebase + Local |
| **HARDWARE** | Sensor status, actuator actions | MEDIUM | Local only |
| **SYSTEM** | App lifecycle, memory, CPU | LOW | Local only |
| **ERROR** | Exceptions, failures | CRITICAL | Firebase + Local |
| **AUDIT** | User actions, access logs | HIGH | Firebase |
| **PERFORMANCE** | Timing, throughput | LOW | Local (rotating) |

---

## 3. Log Levels

```python
CRITICAL = 50  # System crash, data loss
ERROR    = 40  # Failures requiring attention
WARNING  = 30  # Recoverable issues
INFO     = 20  # Normal operations
DEBUG    = 10  # Detailed debugging
```

### Level Usage:

| Level | When to Use | Example |
|-------|-------------|---------|
| CRITICAL | System cannot continue | Firebase connection lost for 1 hour |
| ERROR | Operation failed | Package measurement failed |
| WARNING | Potential issue | Sensor reading out of range |
| INFO | Normal operation | Package classified as EXPRESS |
| DEBUG | Development only | Raw sensor values |

---

## 4. Storage Strategy: Hybrid Approach

```
┌─────────────────────────────────────────────────────────────────────┐
│                         LOG FLOW                                    │
└─────────────────────────────────────────────────────────────────────┘

  Application
      │
      ├──────────────────────────────────────────────────────┐
      │                                                      │
      ▼                                                      ▼
┌─────────────────┐                              ┌─────────────────┐
│   LOCAL LOGS    │                              │  FIREBASE LOGS  │
│   (SD Card)     │                              │    (Cloud)      │
├─────────────────┤                              ├─────────────────┤
│ • All levels    │                              │ • ERROR+        │
│ • Rotating      │                              │ • AUDIT only    │
│ • 7 days max    │                              │ • 30 days max   │
│ • Fast writes   │                              │ • Async upload  │
└─────────────────┘                              └─────────────────┘
        │                                                │
        │         ┌─────────────────┐                   │
        └────────►│  LOG SYNCER     │◄──────────────────┘
                  │  (Background)   │
                  │                 │
                  │ Uploads local   │
                  │ logs to Firebase│
                  │ when online     │
                  └─────────────────┘
```

### Why Hybrid?

| Approach | Pros | Cons |
|----------|------|------|
| **Local Only** | Fast, works offline | No remote access |
| **Cloud Only** | Remote access | Fails when offline |
| **Hybrid** ✅ | Best of both | More complex |

---

## 5. Retention Policy

| Storage | Retention | Max Size | Rotation |
|---------|-----------|----------|----------|
| **Local - Main** | 7 days | 50 MB | Daily rotate |
| **Local - Error** | 30 days | 20 MB | When full |
| **Firebase - Error** | 30 days | Unlimited | Auto-cleanup |
| **Firebase - Audit** | 90 days | Unlimited | Manual archive |

### Space Management:

```python
# Max total local storage: 100 MB
LOCAL_LOG_LIMITS = {
    'main': {'max_size': 50 * 1024 * 1024, 'backup_count': 7},
    'error': {'max_size': 20 * 1024 * 1024, 'backup_count': 30},
    'hardware': {'max_size': 20 * 1024 * 1024, 'backup_count': 7},
    'performance': {'max_size': 10 * 1024 * 1024, 'backup_count': 3}
}
```

---

## 6. Log Format

### Local Logs (Text):
```
2026-01-15 23:26:32.123 | INFO     | measurement | Package measured | id=PKG_001 type=EXPRESS weight=850g
2026-01-15 23:26:33.456 | ERROR    | firebase    | Sync failed      | error=timeout retry=3
2026-01-15 23:26:34.789 | WARNING  | hardware    | Sensor drift     | sensor=HX711 drift=2.5%
```

### Firebase Logs (JSON):
```json
{
  "timestamp": "2026-01-15T23:26:32.123Z",
  "level": "ERROR",
  "category": "firebase",
  "message": "Sync failed",
  "data": {
    "error": "timeout",
    "retry_count": 3,
    "package_id": "PKG_001"
  },
  "device_id": "RPi_001",
  "session_id": "sess_abc123"
}
```

---

## 7. Implementation Plan

### File Structure:
```
sorting_system/
├── logs/                           # Log output directory
│   ├── main.log                    # Current main log
│   ├── main.log.1                  # Rotated (yesterday)
│   ├── error.log                   # Error-only log
│   ├── hardware.log                # Hardware events
│   └── .sync_status                # Firebase sync tracking
│
├── core/
│   └── logger.py                   # Main logging module
│
└── config/
    └── logging_config.py           # Logging configuration
```

### Module Design:

```python
# core/logger.py

class SortingLogger:
    """Central logging handler for sorting system"""
    
    def __init__(self):
        self.local_handler = LocalLogHandler()
        self.firebase_handler = FirebaseLogHandler()
        self.sync_queue = Queue()
    
    def operation(self, message, **data):
        """Log package operations"""
        self._log(INFO, 'operation', message, data)
    
    def hardware(self, component, status, **data):
        """Log hardware events"""
        self._log(INFO, 'hardware', f"{component}: {status}", data)
    
    def error(self, message, exception=None, **data):
        """Log errors - syncs to Firebase"""
        self._log(ERROR, 'error', message, data, sync=True)
    
    def audit(self, action, user=None, **data):
        """Log audit events - always syncs to Firebase"""
        self._log(INFO, 'audit', action, data, sync=True)
```

---

## 8. Best Practices for IoT/Embedded

### ✅ DO:

1. **Use async logging** - Don't block main thread
2. **Buffer writes** - Reduce SD card wear
3. **Rotate logs** - Prevent disk full
4. **Include context** - device_id, session_id
5. **Timestamp in ISO format** - Easy parsing
6. **Log at boundaries** - Entry/exit of operations

### ❌ DON'T:

1. **Log sensitive data** - No passwords, tokens
2. **Log in tight loops** - Performance killer
3. **Use print()** - Use proper logger
4. **Ignore log levels** - Not everything is ERROR
5. **Skip rotation** - SD card will fill up

### 🔄 SYNC Strategy:

```python
# Offline-first approach
1. Write to local immediately
2. Queue for Firebase sync
3. Background worker uploads
4. Mark synced in local status file
5. Retry failed syncs with backoff
```

---

## 9. Trade-offs Discussion

### Performance vs Completeness

| Approach | Performance | Debugging Power |
|----------|-------------|-----------------|
| Minimal logging | ⚡ Fast | ❌ Hard to debug |
| Full logging | 🐌 Slow | ✅ Easy debug |
| **Smart logging** ✅ | ⚡ Fast | ✅ Good enough |

**Recommendation:** Log operations at INFO, hardware at DEBUG (disable in production), errors always.

### Local vs Cloud

| Scenario | Best Storage |
|----------|--------------|
| Quick debugging on-site | Local (instant access) |
| Remote troubleshooting | Cloud (accessible anywhere) |
| Audit compliance | Cloud (tamper-proof) |
| High-frequency events | Local (no network latency) |

### Real-time vs Batched

| Mode | Use Case |
|------|----------|
| Real-time | Errors, critical events |
| Batched (1 min) | Normal operations |
| Batched (5 min) | Performance metrics |

---

## 10. Implementation Priority

| Phase | Task | Priority |
|-------|------|----------|
| 1 | Create `core/logger.py` with local handler | HIGH |
| 2 | Add rotating file handler | HIGH |
| 3 | Integrate with existing code | HIGH |
| 4 | Add Firebase error sync | MEDIUM |
| 5 | Add audit logging | MEDIUM |
| 6 | Add performance logging | LOW |
| 7 | Add log viewer in dashboard | LOW |

---

## 11. Example Usage

```python
from core.logger import get_logger

log = get_logger()

# Normal operation
log.operation("Package measured", 
    package_id="PKG_001",
    service_type="EXPRESS",
    weight=850)

# Hardware event
log.hardware("HX711", "reading", 
    raw_value=12345,
    calibrated=850.5)

# Error with exception
try:
    save_to_firebase(data)
except Exception as e:
    log.error("Firebase save failed",
        exception=e,
        package_id="PKG_001",
        retry_count=3)

# Audit trail
log.audit("package_measured",
    user="operator_1",
    source="web_dashboard")
```

---

## 12. Monitoring & Alerts

### Future Enhancement:

```
Firebase Functions (optional)
         │
         ▼
┌─────────────────┐
│  Error Counter  │
│  per 5 minutes  │
└────────┬────────┘
         │
         ▼ If > threshold
┌─────────────────┐
│  Send Alert     │
│  (Email/Slack)  │
└─────────────────┘
```

---

*Document Version: 1.0*
*Last Updated: 15 Januari 2026*
