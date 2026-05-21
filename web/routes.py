"""
Flask Routes
Main pages and API endpoints for Sorting System
With Firebase Integration, Real-time Updates, and Logging
"""

from flask import Blueprint, render_template, jsonify, request, Response
from datetime import datetime
import json
import queue
import threading

from web.measurement_bridge import (
    should_use_file_bridge, get_measurement_from_file,
    classify_package, MeasurementBridgeError
)
from web.mode_helper import get_system_mode_info

_MODE_INFO = get_system_mode_info()

# Import logger
try:
    from core.logger import get_logger
    log = get_logger()
except ImportError:
    # Fallback if logger not available
    class DummyLogger:
        def info(self, msg, **kw): print(f"[INFO] {msg}")
        def error(self, msg, **kw): print(f"[ERROR] {msg}")
        def warning(self, msg, **kw): print(f"[WARNING] {msg}")
        def operation(self, msg, **kw): print(f"[OPERATION] {msg}")
        def audit(self, msg, **kw): print(f"[AUDIT] {msg}")
    log = DummyLogger()

# Create blueprints
main_bp = Blueprint('main', __name__)
api_bp = Blueprint('api', __name__)

# =============================================================================
# Storage Backend (Firebase or In-Memory)
# =============================================================================

# Event queue for SSE (Server-Sent Events)
_event_queues = []
_event_lock = threading.Lock()

# Try to use Firebase, fallback to in-memory
_storage = None
_use_firebase = False

def get_storage():
    """Get or initialize storage backend"""
    global _storage, _use_firebase
    
    if _storage is None:
        try:
            from storage.firebase_handler import create_storage_handler
            _storage = create_storage_handler("auto")
            _storage.connect()
            _use_firebase = True
            log.info("Firebase storage initialized", backend="firebase")
        except Exception as e:
            log.warning("Firebase not available, using in-memory", error=str(e))
            _storage = InMemoryStorage()
            _use_firebase = False
    
    return _storage


class InMemoryStorage:
    """Fallback in-memory storage if Firebase not available"""
    
    def __init__(self):
        self.packages = []
        self._next_id = 1
    
    def save_package(self, package_data):
        package_id = self._next_id
        self._next_id += 1
        
        package = {
            'id': package_id,
            'timestamp': datetime.now().isoformat(),
            **package_data
        }
        self.packages.append(package)
        return str(package_id)
    
    def get_package(self, package_id):
        for p in self.packages:
            if str(p['id']) == str(package_id):
                return p
        return None
    
    def get_all_packages(self, limit=100):
        return self.packages[-limit:][::-1]  # Newest first
    
    def get_statistics(self):
        total = len(self.packages)
        revenue = sum(p.get('price', 0) for p in self.packages)
        
        by_type = {
            'REGULER': {'count': 0, 'revenue': 0},
            'EXPRESS': {'count': 0, 'revenue': 0},
            'KARGO': {'count': 0, 'revenue': 0}
        }
        
        for p in self.packages:
            stype = p.get('service_type', 'UNKNOWN')
            if stype in by_type:
                by_type[stype]['count'] += 1
                by_type[stype]['revenue'] += p.get('price', 0)
        
        return {
            'total_packages': total,
            'total_revenue': revenue,
            'by_service_type': by_type
        }
    
    def reset_data(self):
        self.packages = []
        self._next_id = 1
        return True


# System status (always in-memory for runtime state)
system_status = {
    'mode': _MODE_INFO['mode_id'],
    'mode_info': _MODE_INFO,
    'is_running': False,
    'last_package': None,
    'total_today': {
        'REGULER': 0,
        'EXPRESS': 0,
        'KARGO': 0
    }
}


# =============================================================================
# Main Page Routes
# =============================================================================

@main_bp.route('/')
def index():
    """Redirect to dashboard"""
    storage = get_storage()
    packages = storage.get_all_packages(10)
    
    return render_template('dashboard.html', 
                          status=system_status,
                          history=packages)


@main_bp.route('/dashboard')
def dashboard():
    """Main monitoring dashboard"""
    storage = get_storage()
    packages = storage.get_all_packages(10)
    
    return render_template('dashboard.html',
                          status=system_status,
                          history=packages)


@main_bp.route('/history')
def history():
    """Package history page"""
    storage = get_storage()
    packages = storage.get_all_packages(100)
    
    return render_template('history.html',
                          packages=packages,
                          status=system_status)


@main_bp.route('/manual')
def manual():
    """Manual measurement page"""
    return render_template('manual.html',
                          status=system_status)


# =============================================================================
# API Endpoints
# =============================================================================

@api_bp.route('/status', methods=['GET'])
def get_status():
    """Get current system status"""
    storage = get_storage()
    stats = storage.get_statistics()
    
    return jsonify({
        'success': True,
        'data': {
            'mode': system_status['mode'],
            'mode_info': system_status['mode_info'],
            'is_running': system_status['is_running'],
            'last_package': system_status['last_package'],
            'statistics': stats.get('by_service_type', system_status['total_today']),
            'storage_backend': 'firebase' if _use_firebase else 'memory',
            'timestamp': datetime.now().isoformat()
        }
    })


@api_bp.route('/measure', methods=['POST'])
def trigger_measurement():
    """Trigger a measurement cycle"""
    global system_status
    
    # Check if already running
    if system_status['is_running']:
        return jsonify({
            'success': False,
            'error': 'System is already running a measurement cycle'
        }), 409
    
    # Set running flag
    system_status['is_running'] = True
    
    try:
        from config.settings import (
            is_mock_mode, HARDWARE_MODE, MEASUREMENT_MODE,
            MEASUREMENT_SOURCE_PATH, PROGRAM_PYTHON_BASE,
            MEASUREMENT_MAX_AGE_SECONDS
        )

        storage = get_storage()
        use_file = should_use_file_bridge(HARDWARE_MODE, MEASUREMENT_MODE)

        if use_file:
            result = get_measurement_from_file(
                MEASUREMENT_SOURCE_PATH,
                PROGRAM_PYTHON_BASE,
                MEASUREMENT_MAX_AGE_SECONDS
            )

            service_type, price = classify_package(result.chargeable_weight)

            package_data = {
                'dimensions': {
                    'panjang': result.panjang,
                    'lebar': result.lebar,
                    'tinggi': result.tinggi
                },
                'weight': {
                    'aktual': result.berat_aktual,
                    'volumetrik': result.berat_volumetrik,
                    'chargeable': result.chargeable_weight,
                    'source': result.chargeable_source
                },
                'measurement_id': result.measurement_id,
                'service_type': service_type,
                'price': price,
                'detection_image': result.detection_image,
                'synced_to_firebase': _use_firebase,
                'data_source': 'file_bridge'
            }

            package_id = storage.save_package(package_data)

            log.operation("Package measured (file bridge)",
                package_id=package_id,
                measurement_id=result.measurement_id,
                service_type=service_type,
                weight=result.chargeable_weight,
                price=price,
                synced=_use_firebase)

            package = {
                'id': package_id,
                'timestamp': result.timestamp,
                **package_data
            }

            system_status['last_package'] = package
            system_status['total_today'][service_type] += 1

            broadcast_event('package_added', {
                'package': package,
                'statistics': {
                    'total_today': sum(system_status['total_today'].values()),
                    'by_type': dict(system_status['total_today'])
                }
            })

            return jsonify({
                'success': True,
                'data': package
            })

        elif is_mock_mode():
            import random

            panjang = round(random.uniform(5, 23), 1)
            lebar = round(random.uniform(5, 23), 1)
            tinggi = round(random.uniform(5, 23), 1)
            berat_aktual = round(random.uniform(50, 2000), 1)
            berat_volumetrik = round((panjang * lebar * tinggi) / 6000 * 1000, 1)
            chargeable = max(berat_aktual, berat_volumetrik)

            service_type, price = classify_package(chargeable)

            package_data = {
                'dimensions': {
                    'panjang': panjang,
                    'lebar': lebar,
                    'tinggi': tinggi
                },
                'weight': {
                    'aktual': berat_aktual,
                    'volumetrik': berat_volumetrik,
                    'chargeable': chargeable
                },
                'service_type': service_type,
                'price': price,
                'synced_to_firebase': _use_firebase,
                'data_source': 'mock'
            }

            package_id = storage.save_package(package_data)

            log.operation("Package measured (mock)",
                package_id=package_id,
                service_type=service_type,
                weight=chargeable,
                price=price,
                synced=_use_firebase)

            package = {
                'id': package_id,
                'timestamp': datetime.now().isoformat(),
                **package_data
            }

            system_status['last_package'] = package
            system_status['total_today'][service_type] += 1

            broadcast_event('package_added', {
                'package': package,
                'statistics': {
                    'total_today': sum(system_status['total_today'].values()),
                    'by_type': dict(system_status['total_today'])
                }
            })

            return jsonify({
                'success': True,
                'data': package
            })

        else:
            return jsonify({
                'success': False,
                'error': 'Mode pengukuran tidak dikenali. '
                         'Set MEASUREMENT_MODE=file atau MEASUREMENT_MODE=mock.'
            }), 501
            
    except MeasurementBridgeError as e:
        log.warning("Measurement bridge error", error=str(e))
        return jsonify({
            'success': False,
            'error': str(e),
            'error_type': 'measurement_bridge'
        }), 422
    except Exception as e:
        log.error("Measurement failed", exception=e)
        return jsonify({
            'success': False,
            'error': 'Terjadi kesalahan sistem. Silakan coba lagi.'
        }), 500
    finally:
        system_status['is_running'] = False


@api_bp.route('/history', methods=['GET'])
def get_history():
    """Get package history from Firebase or memory"""
    storage = get_storage()
    
    # Query parameters
    limit = request.args.get('limit', 50, type=int)
    offset = request.args.get('offset', 0, type=int)
    service_type = request.args.get('type', None)
    
    # Get packages from storage
    all_packages = storage.get_all_packages(limit + offset + 100)  # Get enough for filtering
    
    # Filter by type if specified
    if service_type:
        filtered = [p for p in all_packages if p.get('service_type') == service_type]
    else:
        filtered = all_packages
    
    # Apply pagination
    paginated = filtered[offset:offset + limit]
    
    return jsonify({
        'success': True,
        'data': {
            'packages': paginated,
            'total': len(filtered),
            'limit': limit,
            'offset': offset,
            'source': 'firebase' if _use_firebase else 'memory'
        }
    })


@api_bp.route('/history/<package_id>', methods=['GET'])
def get_package(package_id):
    """Get single package by ID"""
    storage = get_storage()
    package = storage.get_package(package_id)
    
    if package:
        return jsonify({
            'success': True,
            'data': package
        })
    
    return jsonify({
        'success': False,
        'error': f'Package {package_id} not found'
    }), 404


@api_bp.route('/statistics', methods=['GET'])
def get_statistics():
    """Get sorting statistics from Firebase or memory"""
    storage = get_storage()
    stats = storage.get_statistics()
    
    return jsonify({
        'success': True,
        'data': {
            'total_packages': stats.get('total_packages', 0),
            'total_revenue': stats.get('total_revenue', 0),
            'by_service_type': stats.get('by_service_type', {}),
            'source': 'firebase' if _use_firebase else 'memory',
            'timestamp': datetime.now().isoformat()
        }
    })


@api_bp.route('/reset', methods=['POST'])
def reset_statistics():
    """Reset daily statistics (for testing)"""
    global system_status
    
    storage = get_storage()
    
    # Reset storage if it has reset_data method
    if hasattr(storage, 'reset_data'):
        storage.reset_data()
    
    # Reset runtime status
    system_status['total_today'] = {
        'REGULER': 0,
        'EXPRESS': 0,
        'KARGO': 0
    }
    system_status['last_package'] = None
    
    return jsonify({
        'success': True,
        'message': 'Statistics reset successfully',
        'storage_reset': _use_firebase
    })


@api_bp.route('/sync', methods=['POST'])
def force_sync():
    """Force sync status with Firebase"""
    storage = get_storage()
    
    if _use_firebase and hasattr(storage, 'update_system_status'):
        storage.update_system_status('synced')
        return jsonify({
            'success': True,
            'message': 'Synced with Firebase'
        })
    
    return jsonify({
        'success': False,
        'message': 'Firebase not connected'
    }), 400

# =============================================================================
# Server-Sent Events (SSE) for Real-time Updates
# =============================================================================

def broadcast_event(event_type: str, data: dict):
    """
    Broadcast event to all connected SSE clients
    
    Args:
        event_type: Event name (e.g., 'package_added', 'stats_updated')
        data: Event data to send
    """
    with _event_lock:
        dead_queues = []
        for q in _event_queues:
            try:
                q.put_nowait({
                    'event': event_type,
                    'data': data,
                    'timestamp': datetime.now().isoformat()
                })
            except Exception:
                dead_queues.append(q)
        
        # Remove disconnected clients
        for q in dead_queues:
            _event_queues.remove(q)


@api_bp.route('/events', methods=['GET'])
def stream_events():
    """
    SSE endpoint for real-time dashboard updates
    
    Client connects and receives events as they happen:
    - package_added: New package measured
    - stats_updated: Statistics changed
    - system_status: System status changed
    
    Usage:
        const evtSource = new EventSource('/api/events');
        evtSource.onmessage = (e) => { console.log(e.data); };
    """
    def event_stream():
        # Create queue for this client
        q = queue.Queue(maxsize=100)
        
        with _event_lock:
            _event_queues.append(q)
        
        try:
            # Send initial connection event
            yield f"data: {json.dumps({'event': 'connected', 'timestamp': datetime.now().isoformat()})}\n\n"
            
            # Keep connection alive and send events
            while True:
                try:
                    # Wait for event with timeout (for keepalive)
                    event = q.get(timeout=30)
                    yield f"data: {json.dumps(event)}\n\n"
                except queue.Empty:
                    # Send keepalive ping
                    yield ": keepalive\n\n"
                    
        finally:
            with _event_lock:
                if q in _event_queues:
                    _event_queues.remove(q)
    
    return Response(
        event_stream(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no'
        }
    )


@api_bp.route('/events/test', methods=['POST'])
def test_event():
    """Test SSE by broadcasting a test event"""
    broadcast_event('test', {
        'message': 'SSE test event',
        'connected_clients': len(_event_queues)
    })
    
    return jsonify({
        'success': True,
        'connected_clients': len(_event_queues)
    })
