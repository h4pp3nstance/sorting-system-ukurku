# Firebase Optimization Guide

## 1. Setup Database Rules & Indexes

Untuk mengoptimalkan query di Firebase Realtime Database, apply rules berikut:

### Steps to Apply Rules:

1. Buka [Firebase Console](https://console.firebase.google.com)
2. Pilih project "Ukurku" 
3. Go to **Realtime Database** → **Rules**
4. Replace dengan rules berikut:

```json
{
  "rules": {
    ".read": true,
    ".write": true,
    
    "packages": {
      ".indexOn": ["timestamp", "service_type"]
    },
    
    "statistics": {
      ".read": true,
      ".write": true
    },
    
    "system": {
      ".read": true,
      ".write": true
    }
  }
}
```

5. Klik **Publish**

### Why These Rules?

- `.indexOn: ["timestamp", "service_type"]` - Enables efficient queries:
  - Sort packages by timestamp (newest first)
  - Filter packages by service type
  - Required for `order_by_child()` queries

---

## 2. Real-time Dashboard Updates

Dashboard sekarang menggunakan **Server-Sent Events (SSE)** untuk update real-time:

### How It Works:

1. Dashboard connects to `/api/events` endpoint
2. Server broadcasts events when packages are measured
3. Dashboard updates automatically without page refresh

### Events:

| Event | Description |
|-------|-------------|
| `package_added` | New package measured - updates stats & table |
| `stats_updated` | Statistics changed |
| `connected` | Initial connection confirmation |

### JavaScript Integration:

```javascript
// Already implemented in dashboard.html
const evtSource = new EventSource('/api/events');

evtSource.onmessage = (event) => {
    const data = JSON.parse(event.data);
    // Handle event...
};
```

---

## 3. Performance Optimizations

### Current Optimizations:

1. **No-index fallback** - `get_all_packages()` fetches all data and sorts in-memory if index unavailable
2. **Limit queries** - Always specify limit to reduce data transfer
3. **Event broadcasting** - Uses queues for efficient multi-client updates

### Recommended Settings:

```python
# In routes.py, adjust limits based on usage:
DEFAULT_HISTORY_LIMIT = 50  # Balance between UX and performance
MAX_HISTORY_LIMIT = 200     # Cap for API queries
SSE_KEEPALIVE = 30          # Seconds between keepalive pings
```

---

## 4. Testing Real-time Features

### Test SSE Connection:

```bash
# Terminal 1: Start server
cd sorting_system
python run.py

# Terminal 2: Connect to SSE
curl -N http://localhost:5000/api/events
```

### Test Event Broadcast:

```bash
# Send test event
curl -X POST http://localhost:5000/api/events/test
```

### Test Measure with Real-time:

1. Open dashboard in browser
2. In another terminal: `curl -X POST http://localhost:5000/api/measure`
3. Watch dashboard update automatically!

---

## 5. Troubleshooting

### "Index not defined" Error:

Apply the rules in Step 1 above.

### SSE Not Connecting:

1. Check browser console for errors
2. Ensure server is running
3. Check for CORS issues (shouldn't happen with same-origin)

### Data Not Syncing:

1. Check Firebase credentials are valid
2. Verify network connection
3. Check console for error messages

---

## 6. File Locations

| File | Purpose |
|------|---------|
| `config/firebase_rules.json` | Template for database rules |
| `config/firebase_credentials.json` | Service account (gitignored) |
| `storage/firebase_handler.py` | Firebase handler with listeners |
| `web/routes.py` | SSE endpoint & broadcast |
| `web/templates/dashboard.html` | Real-time JavaScript |

