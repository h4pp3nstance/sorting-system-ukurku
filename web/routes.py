"""
Flask Routes
Main pages and API endpoints for Sorting System
With SQLite storage, real-time updates (SSE), and logging
"""

from flask import Blueprint, render_template, jsonify, request, Response, redirect, url_for, flash
from datetime import datetime
import json
import queue
import threading

from web.measurement_bridge import (
    should_use_file_bridge, get_measurement_from_file,
    classify_package, MeasurementBridgeError
)
from web.mode_helper import get_system_mode_info
from web.auth import (
    role_required, api_login_required, api_role_required, current_user,
    ROLE_MITRA, ROLE_MPC, ROLE_ADMIN,
)

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
# Storage Backend (SQLite default, in-memory fallback)
# =============================================================================

# Event queue for SSE (Server-Sent Events)
_event_queues = []
_event_lock = threading.Lock()

_storage = None
_storage_backend = "memory"

def get_storage():
    """Get or initialize storage backend.

    Default: SQLite (offline-first). Override via STORAGE_MODE env
    (sqlite|memory). Falls back to in-memory on any init error.
    """
    global _storage, _storage_backend

    if _storage is None:
        import os
        mode = os.getenv("STORAGE_MODE", "sqlite").lower()
        try:
            from storage.factory import create_storage_handler
            if mode == "sqlite":
                db_path = os.getenv("DB_PATH") or None
                _storage = create_storage_handler("sqlite", db_path=db_path)
            else:
                _storage = create_storage_handler(mode)
            _storage.connect()
            _storage_backend = mode
            log.info("Storage initialized", backend=mode)
        except Exception as e:
            log.warning("Storage init failed, using in-memory", error=str(e))
            _storage = InMemoryStorage()
            _storage_backend = "memory"

    return _storage


class InMemoryStorage:
    """Fallback in-memory storage if SQLite not available"""
    
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

    def update_package_parties(self, package_id, sender=None, recipient=None):
        for p in self.packages:
            if str(p['id']) == str(package_id):
                if sender is not None:
                    p['sender'] = sender
                if recipient is not None:
                    p['recipient'] = recipient
                return True
        return False


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

def _scope_packages(packages):
    """Filter packages to the current Mitra's own data.

    Mitra users see only packages tagged with their mitra_id. Admin/MPC or
    sessions without a mitra_id (e.g. tests) see everything unchanged.
    """
    user = current_user()
    if not user or user.get('role') != ROLE_MITRA:
        return packages
    mitra_id = user.get('mitra_id')
    if not mitra_id:
        return packages
    return [p for p in packages if p.get('mitra_id') == mitra_id]


def _get_scoped_package(package_id):
    """Fetch a package only if the current user is allowed to see it.

    Mitra users can only access packages tagged with their own mitra_id.
    Admin/MPC or sessions without a mitra_id get the package unchanged.
    Returns None if not found OR not owned by the requesting Mitra (IDOR guard).
    """
    package = get_storage().get_package(package_id)
    if not package:
        return None
    user = current_user()
    if not user or user.get('role') != ROLE_MITRA:
        return package
    mitra_id = user.get('mitra_id')
    if not mitra_id:
        return package
    if package.get('mitra_id') != mitra_id:
        return None
    return package


@main_bp.route('/')
def landing():
    """Public landing page with role selection."""
    return render_template('landing.html',
                          mode_info=_MODE_INFO)


@main_bp.route('/dashboard')
@role_required(ROLE_MITRA)
def dashboard():
    """Main monitoring dashboard (Mitra)"""
    storage = get_storage()
    packages = _scope_packages(storage.get_all_packages(100))[:10]
    
    return render_template('dashboard.html',
                          status=system_status,
                          history=packages)


@main_bp.route('/peringatan')
@role_required(ROLE_MITRA)
def mitra_notifications():
    """Daftar peringatan dari MPC untuk Mitra ini."""
    from web import mpc_store
    user = current_user() or {}
    mitra_id = user.get('mitra_id')
    notifications = mpc_store.list_notifications(to_mitra_id=mitra_id)
    return render_template('peringatan.html',
                          status=system_status,
                          notifications=notifications)


@api_bp.route('/notifications/read', methods=['POST'])
@api_login_required
def api_notification_read():
    """Tandai sebuah peringatan sudah dibaca."""
    from web import mpc_store
    payload = request.get_json(silent=True) or {}
    try:
        notif_id = int(payload.get('id'))
    except (TypeError, ValueError):
        return jsonify({'success': False, 'error': 'ID tidak valid.'}), 422
    ok = mpc_store.mark_read(notif_id)
    return jsonify({'success': ok})


def _send_validation_notification(package_id, to_mitra_id, result,
                                  source_label='validasi'):
    """Kirim notifikasi ke Mitra untuk SEMUA 3 status (valid/perlu_review/
    tidak_sesuai). Title + message disesuaikan per status biar Mitra langsung
    paham hasilnya. Idempotent dari sisi caller (create_notification append).
    """
    from web import mpc_store
    status = result.get('status')
    status_label = result.get('status_label') or status or '-'
    if status == 'valid':
        title = 'Validasi Sesuai: Paket #{}'.format(package_id)
        message = ('Paket #{} telah diukur ulang oleh MPC ({}) dan hasilnya '
                   'SESUAI dengan pengukuran Anda.').format(
                       package_id, source_label)
    elif status == 'perlu_review':
        title = 'Validasi Perlu Review: Paket #{}'.format(package_id)
        message = ('Paket #{} diukur ulang oleh MPC ({}) dan terdapat selisih '
                   'kecil. Mohon ditinjau ulang.').format(
                       package_id, source_label)
    else:
        title = 'Validasi Tidak Sesuai: Paket #{}'.format(package_id)
        message = ('Paket #{} diukur ulang oleh MPC ({}) dan hasilnya '
                   'BERBEDA signifikan ({}). Mohon ditindaklanjuti.').format(
                       package_id, source_label, status_label)
    try:
        mpc_store.create_notification(
            package_id=package_id,
            to_mitra_id=to_mitra_id,
            title=title,
            message=message,
            status=status,
        )
    except Exception:
        # Notif gagal tidak boleh blocking response validasi.
        pass


# Set measurement_id yang sudah di-handle oleh validasi web (in-process).
# Box_poller akan skip save_package untuk mid ini supaya tidak dobel ingest.
# Auto-cleanup setelah _CLAIMED_MID_TTL_SECONDS supaya tidak grow unbounded.
_claimed_measurement_ids = {}
_claimed_mid_lock = threading.Lock()
_CLAIMED_MID_TTL_SECONDS = 600  # 10 menit cukup; box_poller poll tiap 3 detik.


def claim_measurement_id(mid):
    """Tandai measurement_id sebagai sudah dikonsumsi oleh validasi web."""
    if not mid:
        return
    now = datetime.now()
    with _claimed_mid_lock:
        _claimed_measurement_ids[str(mid)] = now
        expired = [k for k, ts in _claimed_measurement_ids.items()
                   if (now - ts).total_seconds() > _CLAIMED_MID_TTL_SECONDS]
        for k in expired:
            _claimed_measurement_ids.pop(k, None)


def is_measurement_claimed(mid):
    """True kalau mid sudah di-claim validasi web (box_poller harus skip)."""
    if not mid:
        return False
    with _claimed_mid_lock:
        ts = _claimed_measurement_ids.get(str(mid))
        if not ts:
            return False
        if (datetime.now() - ts).total_seconds() > _CLAIMED_MID_TTL_SECONDS:
            _claimed_measurement_ids.pop(str(mid), None)
            return False
        return True


@main_bp.route('/mpc')
@role_required(ROLE_MPC)
def mpc_dashboard():
    """MPC validation dashboard: paket masuk, statistik, peringatan."""
    from web import mpc_store
    storage = get_storage()
    packages = storage.get_all_packages(100)
    validations = {v['package_id']: v for v in mpc_store.list_validations()}
    attempts_by_pkg = {}
    for pkg in packages:
        pid = str(pkg.get('id'))
        attempts_by_pkg[pid] = mpc_store.list_attempts(pid)
    return render_template('mpc.html',
                          status=system_status,
                          packages=packages,
                          validations=validations,
                          attempts_by_pkg=attempts_by_pkg,
                          val_stats=mpc_store.validation_stats(),
                          notifications=mpc_store.list_notifications(),
                          mpc_arm=mpc_store.get_armed())


@main_bp.route('/mpc/validate/<package_id>')
@role_required(ROLE_MPC)
def mpc_validate_page(package_id):
    """Halaman validasi: tampilkan data Mitra + form ukur ulang MPC."""
    from web import mpc_store
    from web.validation_engine import extract_measurement
    storage = get_storage()
    package = storage.get_package(package_id)
    if not package:
        flash('Paket tidak ditemukan.', 'error')
        return redirect(url_for('main.mpc_dashboard'))

    return render_template('validate.html',
                          status=system_status,
                          package=package,
                          mitra_measurement=extract_measurement(package),
                          existing=mpc_store.get_validation(package_id),
                          attempts=mpc_store.list_attempts(package_id))


@api_bp.route('/mpc/validate', methods=['POST'])
@api_login_required
def api_mpc_validate():
    """Proses input ukur ulang MPC -> bandingkan -> simpan + notifikasi."""
    from web import mpc_store
    from web.validation_engine import (
        compare_measurements, extract_measurement,
        STATUS_TIDAK_SESUAI, STATUS_PERLU_REVIEW,
    )
    from web.settings_store import get_tolerances

    payload = request.get_json(silent=True) or {}
    package_id = payload.get('package_id')

    storage = get_storage()
    package = storage.get_package(package_id) if package_id else None
    if not package:
        return jsonify({'success': False,
                        'error': 'Paket tidak ditemukan.'}), 404

    def _num(key):
        try:
            return float(payload.get(key) or 0)
        except (TypeError, ValueError):
            return 0.0

    panjang = _num('panjang')
    lebar = _num('lebar')
    tinggi = _num('tinggi')
    berat_aktual = _num('berat_aktual')
    if panjang <= 0 or lebar <= 0 or tinggi <= 0 or berat_aktual <= 0:
        return jsonify({'success': False,
                        'error': 'Dimensi dan berat MPC harus lebih dari 0.'}), 422

    berat_volumetrik = round((panjang * lebar * tinggi) / 6000 * 1000, 1)
    chargeable = max(berat_aktual, berat_volumetrik)
    mpc_measurement = {
        'panjang': panjang, 'lebar': lebar, 'tinggi': tinggi,
        'berat_aktual': berat_aktual, 'berat_volumetrik': berat_volumetrik,
        'chargeable_weight': chargeable,
    }

    mitra_measurement = extract_measurement(package)
    result = compare_measurements(mitra_measurement, mpc_measurement,
                                  get_tolerances())

    user = current_user() or {}
    mitra_snapshot = extract_measurement(package)
    attempt = mpc_store.add_validation_attempt(
        package_id, mpc_measurement, result,
        mpc_username=user.get('username'),
        catatan=payload.get('catatan'),
        data_source='mpc_manual_input',
        mitra_snapshot=mitra_snapshot,
        sensor_status='manual',
    )

    _send_validation_notification(
        package_id=package_id,
        to_mitra_id=package.get('mitra_id'),
        result=result,
        source_label='input manual',
    )

    broadcast_event('mpc_validated', {
        'package_id': str(package_id),
        'result': result,
        'attempt': attempt,
    })

    return jsonify({'success': True, 'data': {
        'status': result['status'],
        'status_label': result['status_label'],
        'selisih': result['selisih'],
        'breaches': result['breaches'],
        'mpc_measurement': mpc_measurement,
        'attempt_no': attempt['attempt_no'],
    }})


@api_bp.route('/station/status', methods=['GET'])
@api_login_required
def api_station_status():
    """Status stasiun ukur fisik: idle / sedang dipakai mode apa & oleh siapa.

    Termasuk indikator tahap18 (CLI legacy) yang juga klaim kamera saat aktif.
    """
    from web import station_lock, camera_lock, mpc_store
    data = station_lock.status()
    data.update(camera_lock.status_payload())
    data['mpc_arm'] = mpc_store.get_armed()
    return jsonify({'success': True, 'data': data})


@api_bp.route('/mpc/arm', methods=['GET'])
@api_login_required
def api_mpc_arm_status():
    from web import mpc_store
    return jsonify({'success': True, 'data': {'armed': mpc_store.get_armed()}})


@api_bp.route('/mpc/arm', methods=['POST'])
@api_login_required
def api_mpc_arm():
    """Arm sistem untuk re-measure MPC paket terpilih.

    Body JSON: {"package_id": "<id>"}. Pengukuran tahap18 berikutnya akan di-
    klaim sebagai pengukuran MPC untuk paket ini (lewat box_poller).
    """
    from web import mpc_store
    payload = request.get_json(silent=True) or {}
    package_id = payload.get('package_id')
    if not package_id:
        return jsonify({'success': False, 'error': 'package_id wajib.'}), 400

    storage = get_storage()
    if not storage.get_package(package_id):
        return jsonify({'success': False, 'error': 'Paket tidak ditemukan.'}), 404

    user = current_user() or {}
    ok, arm = mpc_store.arm_mpc(package_id, armed_by=user.get('username'))
    if not ok:
        return jsonify({
            'success': False,
            'error': 'Sudah ada paket lain yang menunggu pengukuran ulang.',
            'error_type': 'already_armed',
            'armed': arm,
        }), 409

    broadcast_event('mpc_armed', {'armed': arm})
    return jsonify({'success': True, 'data': {'armed': arm}})


@api_bp.route('/mpc/arm/cancel', methods=['POST'])
@api_login_required
def api_mpc_arm_cancel():
    from web import mpc_store
    user = current_user() or {}
    cleared = mpc_store.cancel_armed(by_user=user.get('username'))
    if cleared:
        broadcast_event('mpc_arm_cancelled', {'armed': cleared})
    return jsonify({'success': True, 'data': {'cancelled': cleared}})


@api_bp.route('/form/draft', methods=['GET'])
@api_login_required
def api_form_draft_get():
    """Return draft pengirim/penerima aktif untuk Mitra saat ini (dashboard restore)."""
    from web import mpc_store
    user = current_user() or {}
    mitra_id = user.get('mitra_id')
    if not mitra_id:
        return jsonify({'success': True, 'data': {'draft': None}})
    draft = mpc_store.get_form_draft(mitra_id)
    return jsonify({'success': True, 'data': {'draft': draft}})


@api_bp.route('/form/draft', methods=['POST'])
@api_login_required
def api_form_draft_save():
    """Simpan/refresh draft pengirim/penerima dari dashboard (debounced auto-save).

    Body JSON: {"sender": {nama, telepon, alamat}, "recipient": {...}}
    Empty/blank payload meng-clear draft. Scope per Mitra (mitra_id session).
    TTL default 5 menit (FORM_DRAFT_DEFAULT_TTL_SECONDS).
    """
    from web import mpc_store
    user = current_user() or {}
    mitra_id = user.get('mitra_id')
    if not mitra_id:
        return jsonify({
            'success': False,
            'error': 'Hanya Mitra yang bisa menyimpan draft form.',
            'error_type': 'not_a_mitra',
        }), 403
    payload = request.get_json(silent=True) or {}
    sender = _extract_party(payload, 'sender') or None
    recipient = _extract_party(payload, 'recipient') or None
    draft = mpc_store.set_form_draft(mitra_id, sender=sender, recipient=recipient)
    return jsonify({'success': True, 'data': {'draft': draft}})


@api_bp.route('/form/draft', methods=['DELETE'])
@api_login_required
def api_form_draft_clear():
    """Hapus draft form (dipakai saat Mitra reset form atau setelah paket masuk)."""
    from web import mpc_store
    user = current_user() or {}
    mitra_id = user.get('mitra_id')
    if not mitra_id:
        return jsonify({'success': True, 'data': {'cleared': None}})
    cleared = mpc_store.clear_form_draft(mitra_id)
    return jsonify({'success': True, 'data': {'cleared': cleared}})


@api_bp.route('/packages/<package_id>/parties', methods=['PATCH'])
@api_login_required
def api_package_update_parties(package_id):
    """Backfill sender/recipient untuk paket existing.

    Dipakai dashboard 'Lengkapi Data Pengirim' untuk paket box_tahap18 lama
    yang masuk tanpa form data. Scope IDOR: Mitra hanya boleh edit paketnya
    sendiri. Wajib salah satu (sender atau recipient) tidak kosong.
    """
    package = _get_scoped_package(package_id)
    if not package:
        return jsonify({
            'success': False,
            'error': 'Paket tidak ditemukan.',
            'error_type': 'not_found',
        }), 404

    payload = request.get_json(silent=True) or {}
    sender = _extract_party(payload, 'sender') or None
    recipient = _extract_party(payload, 'recipient') or None
    if sender is None and recipient is None:
        return jsonify({
            'success': False,
            'error': 'Minimal salah satu (pengirim/penerima) wajib diisi.',
            'error_type': 'empty_payload',
        }), 422

    if sender is not None and not sender.get('nama'):
        return jsonify({
            'success': False,
            'error': 'Nama pengirim tidak boleh kosong.',
            'error_type': 'missing_sender_name',
        }), 422
    if recipient is not None and not recipient.get('nama'):
        return jsonify({
            'success': False,
            'error': 'Nama penerima tidak boleh kosong.',
            'error_type': 'missing_recipient_name',
        }), 422

    storage = get_storage()
    ok = storage.update_package_parties(package_id, sender=sender,
                                         recipient=recipient)
    if not ok:
        return jsonify({
            'success': False,
            'error': 'Gagal memperbarui paket di storage.',
            'error_type': 'storage_error',
        }), 500

    updated = storage.get_package(package_id) or package
    broadcast_event('package_parties_updated', {
        'package_id': package_id,
        'sender': updated.get('sender'),
        'recipient': updated.get('recipient'),
    })
    return jsonify({'success': True, 'data': {'package': updated}})


@api_bp.route('/mpc/measure', methods=['POST'])
@api_login_required
def api_mpc_measure():
    """Validasi MPC OTOMATIS: ukur ulang paket pakai sensor fisik yang sama,
    lalu bandingkan dengan pengukuran Mitra. Menggantikan input manual.

    Alur: kunci stasiun -> measure_real() -> sanity check paket ada ->
    compare vs snapshot Mitra (orientasi dinormalisasi) -> catat attempt ->
    notifikasi Mitra hanya bila hasil final tidak_sesuai/perlu_review.
    """
    from web import mpc_store, station_lock, camera_lock
    from web.validation_engine import (
        compare_measurements, extract_measurement, is_package_present,
    )
    from web.settings_store import get_tolerances
    from web.measurement_engine import (
        measure_real,
        MeasurementUnavailableError,
        NeedCalibrationError,
        MeasurementTimeoutError,
        MeasurementEngineError,
    )

    payload = request.get_json(silent=True) or {}
    package_id = payload.get('package_id')

    storage = get_storage()
    package = storage.get_package(package_id) if package_id else None
    if not package:
        return jsonify({'success': False,
                        'error': 'Paket tidak ditemukan.'}), 404

    cam_ok, cam_msg, cam_pids = camera_lock.ensure_web_can_use_camera()
    if not cam_ok:
        return jsonify({
            'success': False,
            'error': cam_msg,
            'error_type': 'camera_busy_tahap18',
            'tahap18_pids': cam_pids,
        }), 409

    user = current_user() or {}
    ok, st = station_lock.acquire(station_lock.MODE_MPC,
                                  owner=user.get('username'))
    if not ok:
        return jsonify({
            'success': False,
            'error': 'Alat ukur sedang dipakai oleh {} ({}).'.format(
                st.get('owner') or 'pengguna lain', st.get('mode')),
            'error_type': 'station_busy'
        }), 409

    try:
        try:
            mapped = measure_real()
        except camera_lock.CameraBusyError as e:
            return jsonify({
                'success': False,
                'error': str(e),
                'error_type': 'camera_busy_tahap18',
                'tahap18_pids': getattr(e, 'pids', []),
            }), 409
        except NeedCalibrationError as e:
            return jsonify({'success': False,
                            'error': 'Sistem belum dikalibrasi. ' + str(e),
                            'error_type': 'need_calibration'}), 422
        except MeasurementTimeoutError:
            return jsonify({
                'success': False,
                'error': 'Paket tidak terdeteksi. Letakkan paket di area '
                         'ukur lalu coba lagi.',
                'error_type': 'needs_remeasure'}), 422
        except MeasurementUnavailableError:
            return jsonify({
                'success': False,
                'error': 'Perangkat pengukuran tidak tersedia.',
                'error_type': 'sensor_error'}), 503
        except MeasurementEngineError as e:
            return jsonify({'success': False, 'error': str(e),
                            'error_type': 'sensor_error'}), 422

        # measure_real() menulis JSON ke hasil_tahap18/. Claim mid-nya sekarang
        # supaya box_poller skip save_package (tidak nambah row "Paket Masuk"
        # untuk paket validasi).
        claim_measurement_id(mapped.get('measurement_id'))

        mpc_measurement = {
            'panjang': mapped['panjang'], 'lebar': mapped['lebar'],
            'tinggi': mapped['tinggi'],
            'berat_aktual': mapped['berat_aktual'],
            'berat_volumetrik': mapped['berat_volumetrik'],
            'chargeable_weight': mapped['chargeable_weight'],
        }

        if not is_package_present(mpc_measurement):
            return jsonify({
                'success': False,
                'error': 'Paket tidak terdeteksi di alat (berat/dimensi '
                         'mendekati nol). Letakkan paket lalu ukur lagi.',
                'error_type': 'needs_remeasure'}), 422

        mitra_snapshot = extract_measurement(package)
        result = compare_measurements(mitra_snapshot, mpc_measurement,
                                      get_tolerances(),
                                      normalize_orientation=True)

        attempt = mpc_store.add_validation_attempt(
            package_id, mpc_measurement, result,
            mpc_username=user.get('username'),
            catatan=payload.get('catatan'),
            data_source='mpc_in_process',
            mitra_snapshot=mitra_snapshot,
            sensor_status='ok',
        )

        _send_validation_notification(
            package_id=package_id,
            to_mitra_id=package.get('mitra_id'),
            result=result,
            source_label='sensor web',
        )

        broadcast_event('mpc_validated', {
            'package_id': str(package_id),
            'result': result,
            'attempt': attempt,
        })

        return jsonify({'success': True, 'data': {
            'status': result['status'],
            'status_label': result['status_label'],
            'selisih': result['selisih'],
            'breaches': result['breaches'],
            'mpc_measurement': mpc_measurement,
            'attempt_no': attempt['attempt_no'],
        }})
    except Exception as e:
        return jsonify({'success': False,
                        'error': 'Terjadi kesalahan tak terduga: ' + str(e),
                        'error_type': 'server_error'}), 500
    finally:
        station_lock.release()


@main_bp.route('/history/export.csv')
@role_required(ROLE_MITRA)
def history_export_csv():
    """Export riwayat paket (Mitra-scoped) sebagai file CSV."""
    import csv
    import io

    storage = get_storage()
    packages = _scope_packages(storage.get_all_packages(1000))

    service_type = request.args.get('type')
    if service_type:
        packages = [p for p in packages
                    if p.get('service_type') == service_type]

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        'ID', 'Waktu', 'Panjang_cm', 'Lebar_cm', 'Tinggi_cm',
        'Berat_Aktual_g', 'Berat_Volumetrik_g', 'Chargeable_g',
        'Layanan', 'Biaya_Rp',
    ])
    for p in packages:
        dims = p.get('dimensions', {}) or {}
        weight = p.get('weight', {}) or {}
        writer.writerow([
            p.get('id', ''),
            p.get('timestamp', ''),
            dims.get('panjang', ''),
            dims.get('lebar', ''),
            dims.get('tinggi', ''),
            weight.get('aktual', ''),
            weight.get('volumetrik', ''),
            weight.get('chargeable', ''),
            p.get('service_type', ''),
            p.get('price', ''),
        ])

    filename = 'riwayat-paket-' + datetime.now().strftime('%Y%m%d_%H%M%S') + '.csv'
    return Response(
        buf.getvalue(),
        mimetype='text/csv',
        headers={
            'Content-Disposition': 'attachment; filename="' + filename + '"'
        }
    )


@main_bp.route('/admin')
@role_required(ROLE_ADMIN)
def admin_dashboard():
    """Admin management dashboard (placeholder, Phase 1)."""
    storage = get_storage()
    stats = storage.get_statistics()
    from web.auth import list_users
    from web.settings_store import load_settings
    users = list_users()
    return render_template('admin.html',
                          status=system_status,
                          stats=stats,
                          users=users,
                          user_count=len(users),
                          settings=load_settings(),
                          all_packages=storage.get_all_packages(100))


@main_bp.route('/admin/db')
@role_required(ROLE_ADMIN)
def admin_db_viewer():
    """Halaman SQLite viewer (read-only, admin-only) - pengganti DBeaver."""
    from web.db_viewer import list_tables
    try:
        tables = list_tables()
        error = None
    except Exception as e:
        tables = []
        error = str(e)
    return render_template('admin_db.html',
                          status=system_status,
                          tables=tables,
                          db_error=error)


@api_bp.route('/admin/db/table/<name>', methods=['GET'])
@api_role_required(ROLE_ADMIN)
def api_db_table(name):
    """Baris + skema satu tabel (read-only, paginated)."""
    from web.db_viewer import table_rows, table_schema
    limit = request.args.get('limit', 100, type=int)
    offset = request.args.get('offset', 0, type=int)
    try:
        data = table_rows(name, limit=limit, offset=offset)
        data['schema'] = table_schema(name)
        return jsonify({'success': True, 'data': data})
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/admin/db/query', methods=['POST'])
@api_role_required(ROLE_ADMIN)
def api_db_query():
    """Jalankan query SELECT read-only (guarded)."""
    from web.db_viewer import run_select
    payload = request.get_json(silent=True) or {}
    sql = payload.get('sql', '')
    try:
        return jsonify({'success': True, 'data': run_select(sql)})
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 422
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@main_bp.route('/admin/users/create', methods=['POST'])
@role_required(ROLE_ADMIN)
def admin_user_create():
    from web.auth import create_user
    ok, err = create_user(
        username=request.form.get('username'),
        password=request.form.get('password'),
        role=request.form.get('role'),
        name=request.form.get('name'),
        mitra_id=request.form.get('mitra_id'),
        mpc_id=request.form.get('mpc_id'),
    )
    flash('User berhasil ditambahkan.' if ok else err,
          'success' if ok else 'error')
    return redirect(url_for('main.admin_dashboard'))


@main_bp.route('/admin/users/update', methods=['POST'])
@role_required(ROLE_ADMIN)
def admin_user_update():
    from web.auth import update_user
    ok, err = update_user(
        username=request.form.get('username'),
        name=request.form.get('name'),
        role=request.form.get('role'),
        password=request.form.get('password') or None,
        mitra_id=request.form.get('mitra_id'),
        mpc_id=request.form.get('mpc_id'),
    )
    flash('User berhasil diperbarui.' if ok else err,
          'success' if ok else 'error')
    return redirect(url_for('main.admin_dashboard'))


@main_bp.route('/admin/users/delete', methods=['POST'])
@role_required(ROLE_ADMIN)
def admin_user_delete():
    from web.auth import delete_user, current_user
    acting = (current_user() or {}).get('username')
    ok, err = delete_user(request.form.get('username'), acting_username=acting)
    flash('User berhasil dihapus.' if ok else err,
          'success' if ok else 'error')
    return redirect(url_for('main.admin_dashboard'))


@main_bp.route('/admin/settings', methods=['POST'])
@role_required(ROLE_ADMIN, ROLE_MITRA)
def admin_settings_update():
    from web.settings_store import update_tolerances, update_tariffs, update_classification
    is_admin = (current_user() or {}).get('role') == ROLE_ADMIN
    section = request.form.get('section')
    # Toleransi (validasi MPC) admin-only; Mitra hanya klasifikasi & tarif.
    if section == 'toleransi' and not is_admin:
        flash('Anda tidak memiliki akses ke pengaturan ini.', 'error')
        return redirect(url_for('main.kalibrasi'))
    if section == 'toleransi':
        update_tolerances(
            dimensi_cm=request.form.get('dimensi_cm'),
            berat_aktual_g=request.form.get('berat_aktual_g'),
            berat_tagihan_g=request.form.get('berat_tagihan_g'),
        )
        flash('Toleransi validasi disimpan.', 'success')
    elif section == 'tarif':
        update_tariffs(
            reguler=request.form.get('reguler'),
            express=request.form.get('express'),
            kargo=request.form.get('kargo'),
        )
        flash('Tarif layanan disimpan.', 'success')
    elif section == 'klasifikasi':
        update_classification(
            reguler_max_g=request.form.get('reguler_max_g'),
            express_max_g=request.form.get('express_max_g'),
            kargo_max_g=request.form.get('kargo_max_g'),
        )
        flash('Ambang klasifikasi berat disimpan.', 'success')
    else:
        flash('Bagian pengaturan tidak dikenali.', 'error')
    if is_admin:
        return redirect(url_for('main.admin_dashboard'))
    return redirect(url_for('main.kalibrasi'))


@main_bp.route('/history')
@role_required(ROLE_MITRA)
def history():
    """Package history page"""
    storage = get_storage()
    packages = _scope_packages(storage.get_all_packages(200))[:100]
    
    return render_template('history.html',
                          packages=packages,
                          status=system_status)


# Indonesian month names for receipt formatting
_INDONESIAN_MONTHS = [
    "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember"
]


def _format_indonesian_datetime(iso_string):
    """Format ISO timestamp as '21 Mei 2026, 14:32' (Indonesian)."""
    if not iso_string:
        return "-"
    try:
        dt = datetime.fromisoformat(iso_string)
    except (ValueError, TypeError):
        return str(iso_string)
    month_name = _INDONESIAN_MONTHS[dt.month - 1]
    return f"{dt.day} {month_name} {dt.year}, {dt.hour:02d}:{dt.minute:02d}"


def _format_indonesian_price(price):
    """Format price as 'Rp 6.000' with Indonesian thousand separator."""
    try:
        amount = float(price or 0)
    except (TypeError, ValueError):
        amount = 0
    return "Rp {:,.0f}".format(amount).replace(",", ".")


def _extract_party(payload, key):
    """Pull a {nama, telepon, alamat} block from request payload, sanitized."""
    block = payload.get(key) or {}
    if not isinstance(block, dict):
        return {}
    party = {}
    for field in ('nama', 'telepon', 'alamat'):
        value = block.get(field)
        if value is not None:
            party[field] = str(value).strip()
    return party


def _package_metadata_from_request():
    """Build sender/recipient/service + mitra identity from request + session.

    Returns a dict to merge into package_data. Empty/absent body yields only
    the mitra identity (preserving legacy behavior for callers with no body).
    """
    payload = request.get_json(silent=True) or {}
    meta = {}

    sender = _extract_party(payload, 'sender')
    recipient = _extract_party(payload, 'recipient')
    if sender:
        meta['sender'] = sender
    if recipient:
        meta['recipient'] = recipient

    user = current_user()
    if user:
        meta['mitra_id'] = user.get('mitra_id')
        meta['mitra_name'] = user.get('name')

    return meta, payload


def _validate_party_fields(meta):
    """Reject jika nama pengirim/penerima kosong. Return None kalau OK,
    atau (response, status) tuple kalau invalid."""
    sender = meta.get('sender') or {}
    recipient = meta.get('recipient') or {}
    if not sender.get('nama'):
        return jsonify({
            'success': False,
            'error': 'Nama pengirim wajib diisi untuk resi.',
            'error_type': 'missing_sender'
        }), 422
    if not recipient.get('nama'):
        return jsonify({
            'success': False,
            'error': 'Nama penerima wajib diisi untuk resi.',
            'error_type': 'missing_recipient'
        }), 422
    return None


@main_bp.route('/receipt/<package_id>')
@role_required(ROLE_MITRA)
def receipt(package_id):
    """Render printable receipt for a package."""
    package = _get_scoped_package(package_id)

    if not package:
        return render_template(
            'dashboard.html',
            status=system_status,
            history=[],
            error="Paket tidak ditemukan"
        ), 404

    package_display_id = "PKT-" + str(package.get('id', '')).zfill(5)
    formatted_timestamp = _format_indonesian_datetime(package.get('timestamp'))
    formatted_price = _format_indonesian_price(package.get('price', 0))
    printed_at = _format_indonesian_datetime(datetime.now().isoformat())

    return render_template(
        'receipt.html',
        package=package,
        package_display_id=package_display_id,
        formatted_timestamp=formatted_timestamp,
        formatted_price=formatted_price,
        printed_at=printed_at,
    )


@main_bp.route('/receipt/<package_id>.pdf')
@role_required(ROLE_MITRA)
def receipt_pdf(package_id):
    """Download receipt as a PDF file."""
    package = _get_scoped_package(package_id)

    if not package:
        return jsonify({
            'success': False,
            'error': 'Paket tidak ditemukan'
        }), 404

    from web.pdf_receipt import build_receipt_pdf
    pdf_bytes = build_receipt_pdf(package)

    filename = "resi-PKT-" + str(package.get('id', '')).zfill(5) + ".pdf"
    return Response(
        pdf_bytes,
        mimetype='application/pdf',
        headers={
            'Content-Disposition': 'attachment; filename="' + filename + '"'
        }
    )


@main_bp.route('/api/evidence/<package_id>')
@role_required(ROLE_MITRA)
def package_evidence(package_id):
    """Serve the detection evidence image for a package (read-only).

    Keyed by package_id (path comes from DB, never the client) + per-mitra
    scope + path confined to PROGRAM_PYTHON_BASE -> path traversal not possible.
    """
    import os
    from flask import send_file
    from config.settings import PROGRAM_PYTHON_BASE

    package = _get_scoped_package(package_id)
    if not package:
        return jsonify({'success': False, 'error': 'Paket tidak ditemukan'}), 404

    rel = (package.get('detection_image') or '').strip()
    if not rel or not PROGRAM_PYTHON_BASE:
        return jsonify({'success': False,
                        'error': 'Bukti gambar tidak tersedia untuk paket ini.'}), 404

    base = os.path.realpath(PROGRAM_PYTHON_BASE)
    target = os.path.realpath(os.path.join(base, rel))
    if not (target == base or target.startswith(base + os.sep)) or not os.path.isfile(target):
        return jsonify({'success': False,
                        'error': 'Bukti gambar tidak ditemukan.'}), 404

    return send_file(target, mimetype='image/jpeg')


@main_bp.route('/manual')
@role_required(ROLE_MITRA)
def manual():
    """Manual measurement page"""
    from web.settings_store import get_classification, get_tariffs
    return render_template('manual.html',
                          status=system_status,
                          klasifikasi=get_classification(),
                          tarif=get_tariffs())


@main_bp.route('/kalibrasi')
@role_required(ROLE_MITRA)
def kalibrasi():
    """Halaman status kalibrasi sensor (read-only dari program-python)."""
    from web.calibration_status import get_calibration_status
    from web.settings_store import get_classification, get_tariffs
    return render_template('kalibrasi.html',
                          status=system_status,
                          calibration=get_calibration_status(),
                          klasifikasi=get_classification(),
                          tarif=get_tariffs())


# =============================================================================
# API Endpoints
# =============================================================================
# API Endpoints
# =============================================================================

@api_bp.route('/status', methods=['GET'])
@api_login_required
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
            'storage_backend': _storage_backend,
            'timestamp': datetime.now().isoformat()
        }
    })


@api_bp.route('/measure', methods=['POST'])
@api_login_required
def trigger_measurement():
    """Trigger a measurement cycle"""
    global system_status
    
    # Check if already running
    if system_status['is_running']:
        return jsonify({
            'success': False,
            'error': 'System is already running a measurement cycle'
        }), 409

    from web import station_lock, camera_lock

    cam_ok, cam_msg, cam_pids = camera_lock.ensure_web_can_use_camera()
    if not cam_ok:
        return jsonify({
            'success': False,
            'error': cam_msg,
            'error_type': 'camera_busy_tahap18',
            'tahap18_pids': cam_pids,
        }), 409

    user = current_user() or {}
    ok, st = station_lock.acquire(station_lock.MODE_MITRA,
                                  owner=user.get('username'))
    if not ok:
        return jsonify({
            'success': False,
            'error': 'Alat ukur sedang dipakai oleh {} ({}). Tunggu '
                     'hingga selesai.'.format(st.get('owner') or 'pengguna lain',
                                              st.get('mode')),
            'error_type': 'station_busy'
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
        package_meta, _payload = _package_metadata_from_request()

        # Server-side guard: tolak request tanpa nama pengirim/penerima.
        # Resi tidak boleh kosong di kolom Pengirim/Penerima.
        invalid_party = _validate_party_fields(package_meta)
        if invalid_party is not None:
            system_status['is_running'] = False
            try:
                station_lock.release(owner=user.get('username'))
            except Exception:
                pass
            return invalid_party

        if MEASUREMENT_MODE == 'in_process':
            from web.measurement_engine import (
                measure_real,
                MeasurementUnavailableError,
                NeedCalibrationError,
                MeasurementTimeoutError,
                MeasurementEngineError,
            )

            try:
                mapped = measure_real()
            except camera_lock.CameraBusyError as e:
                log.warning("Camera busy by tahap18", error=str(e))
                return jsonify({
                    'success': False,
                    'error': str(e),
                    'error_type': 'camera_busy_tahap18',
                    'tahap18_pids': getattr(e, 'pids', []),
                }), 409
            except NeedCalibrationError as e:
                log.warning("Measurement needs calibration", error=str(e))
                return jsonify({
                    'success': False,
                    'error': 'Sistem belum dikalibrasi. ' + str(e),
                    'error_type': 'need_calibration'
                }), 422
            except MeasurementTimeoutError as e:
                log.warning("Measurement timeout", error=str(e))
                return jsonify({
                    'success': False,
                    'error': 'Paket tidak terdeteksi. Pastikan paket berada '
                             'di area ukur, lalu coba lagi.',
                    'error_type': 'timeout'
                }), 422
            except MeasurementUnavailableError as e:
                log.error("Measurement hardware unavailable", error=str(e))
                return jsonify({
                    'success': False,
                    'error': 'Perangkat pengukuran tidak tersedia di sistem ini.',
                    'error_type': 'unavailable'
                }), 503
            except MeasurementEngineError as e:
                log.error("Measurement engine error", error=str(e))
                return jsonify({
                    'success': False,
                    'error': str(e),
                    'error_type': 'measurement_engine'
                }), 422

            service_type, price = classify_package(mapped['chargeable_weight'])

            package_data = {
                'dimensions': {
                    'panjang': mapped['panjang'],
                    'lebar': mapped['lebar'],
                    'tinggi': mapped['tinggi']
                },
                'weight': {
                    'aktual': mapped['berat_aktual'],
                    'volumetrik': mapped['berat_volumetrik'],
                    'chargeable': mapped['chargeable_weight'],
                    'source': mapped['chargeable_source']
                },
                'measurement_id': mapped['measurement_id'],
                'service_type': service_type,
                'price': price,
                'detection_image': mapped['detection_image'],
                'data_source': 'in_process',
                **package_meta
            }

            package_id = storage.save_package(package_data)

            log.operation("Package measured (in-process)",
                package_id=package_id,
                measurement_id=mapped['measurement_id'],
                service_type=service_type,
                weight=mapped['chargeable_weight'],
                price=price,
                backend=_storage_backend)

            package = {
                'id': package_id,
                'timestamp': mapped['timestamp'],
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
                'data_source': 'file_bridge',
                **package_meta
            }

            package_id = storage.save_package(package_data)

            log.operation("Package measured (file bridge)",
                package_id=package_id,
                measurement_id=result.measurement_id,
                service_type=service_type,
                weight=result.chargeable_weight,
                price=price,
                backend=_storage_backend)

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
                'data_source': 'mock',
                **package_meta
            }

            package_id = storage.save_package(package_data)

            log.operation("Package measured (mock)",
                package_id=package_id,
                service_type=service_type,
                weight=chargeable,
                price=price,
                backend=_storage_backend)

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
        station_lock.release()


@api_bp.route('/manual', methods=['POST'])
@api_login_required
def manual_entry():
    """Save a package from manual operator input (alat error / fallback)."""
    payload = request.get_json(silent=True) or {}

    try:
        panjang = float(payload.get('panjang') or 0)
        lebar = float(payload.get('lebar') or 0)
        tinggi = float(payload.get('tinggi') or 0)
        berat_aktual = float(payload.get('berat_aktual') or 0)
    except (TypeError, ValueError):
        return jsonify({
            'success': False,
            'error': 'Dimensi dan berat harus berupa angka.'
        }), 422

    if panjang <= 0 or lebar <= 0 or tinggi <= 0 or berat_aktual <= 0:
        return jsonify({
            'success': False,
            'error': 'Dimensi dan berat harus lebih dari 0.'
        }), 422

    alasan = (payload.get('alasan') or '').strip()
    if not alasan:
        return jsonify({
            'success': False,
            'error': 'Alasan input manual wajib diisi untuk audit.'
        }), 422

    berat_volumetrik = round((panjang * lebar * tinggi) / 6000 * 1000, 1)
    chargeable = max(berat_aktual, berat_volumetrik)
    service_type, price = classify_package(chargeable)

    package_meta, _payload = _package_metadata_from_request()

    invalid_party = _validate_party_fields(package_meta)
    if invalid_party is not None:
        return invalid_party

    storage = get_storage()
    package_data = {
        'dimensions': {
            'panjang': round(panjang, 2),
            'lebar': round(lebar, 2),
            'tinggi': round(tinggi, 2)
        },
        'weight': {
            'aktual': round(berat_aktual, 1),
            'volumetrik': berat_volumetrik,
            'chargeable': chargeable
        },
        'service_type': service_type,
        'price': price,
        'alasan_manual': alasan,
        'data_source': 'manual',
        **package_meta
    }

    package_id = storage.save_package(package_data)

    log.operation("Package measured (manual)",
        package_id=package_id,
        service_type=service_type,
        weight=chargeable,
        price=price,
        reason=alasan,
        backend=_storage_backend)

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


@api_bp.route('/history', methods=['GET'])
@api_login_required
def get_history():
    """Get package history from storage"""
    storage = get_storage()
    
    # Query parameters
    limit = request.args.get('limit', 50, type=int)
    offset = request.args.get('offset', 0, type=int)
    service_type = request.args.get('type', None)
    
    # Get packages from storage
    all_packages = _scope_packages(storage.get_all_packages(limit + offset + 100))
    
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
            'source': _storage_backend
        }
    })


@api_bp.route('/history/<package_id>', methods=['GET'])
@api_login_required
def get_package(package_id):
    """Get single package by ID"""
    package = _get_scoped_package(package_id)
    
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
@api_login_required
def get_statistics():
    """Get sorting statistics from storage"""
    storage = get_storage()
    stats = storage.get_statistics()
    
    return jsonify({
        'success': True,
        'data': {
            'total_packages': stats.get('total_packages', 0),
            'total_revenue': stats.get('total_revenue', 0),
            'by_service_type': stats.get('by_service_type', {}),
            'source': _storage_backend,
            'timestamp': datetime.now().isoformat()
        }
    })


@api_bp.route('/reset', methods=['POST'])
@api_role_required(ROLE_ADMIN)
def reset_statistics():
    """Reset daily statistics (admin only: menghapus data semua mitra)"""
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
        'storage_reset': True
    })


@api_bp.route('/sync', methods=['POST'])
@api_login_required
def force_sync():
    """Sinkronisasi cloud tidak berlaku (penyimpanan lokal SQLite offline-first)."""
    return jsonify({
        'success': False,
        'message': 'Penyimpanan lokal (SQLite). Sinkronisasi cloud tidak diperlukan.'
    }), 400


@api_bp.route('/hardware/status', methods=['GET'])
@api_login_required
def hardware_status():
    """Status koneksi hardware (kamera+GPIO dipegang web atau tidak)."""
    from config.settings import MEASUREMENT_MODE
    try:
        from web.measurement_engine import is_session_active
        connected = is_session_active()
    except Exception:
        connected = False
    return jsonify({
        'success': True,
        'data': {'connected': connected, 'mode': MEASUREMENT_MODE}
    })


@api_bp.route('/box/status', methods=['GET'])
@api_login_required
def box_status():
    """Status box fisik (tombol+lampu) dari tahap17, read-only."""
    from web.box_status import get_box_status
    return jsonify({'success': True, 'data': get_box_status()})


@api_bp.route('/hardware/connect', methods=['POST'])
@role_required(ROLE_MITRA)
def hardware_connect():
    """Klaim kamera+GPIO untuk web (sesi pengukuran in_process)."""
    from web.measurement_engine import (
        connect_session, MeasurementUnavailableError,
        NeedCalibrationError, MeasurementEngineError,
    )
    try:
        result = connect_session()
    except NeedCalibrationError as e:
        return jsonify({'success': False, 'error': 'Belum dikalibrasi. ' + str(e),
                        'error_type': 'need_calibration'}), 422
    except MeasurementUnavailableError as e:
        return jsonify({'success': False, 'error': str(e),
                        'error_type': 'unavailable'}), 503
    except MeasurementEngineError as e:
        return jsonify({'success': False, 'error': str(e)}), 422
    except Exception as e:
        return jsonify({'success': False,
                        'error': 'Gagal connect hardware: ' + str(e)}), 500
    return jsonify({'success': True, 'data': result,
                    'message': 'Hardware terhubung. Kamera & sensor siap.'})


@api_bp.route('/hardware/disconnect', methods=['POST'])
@role_required(ROLE_MITRA)
def hardware_disconnect():
    """Lepas kamera+GPIO supaya program lain (tahap14 standalone) bisa pakai."""
    from web.measurement_engine import disconnect_session
    try:
        result = disconnect_session()
    except Exception as e:
        return jsonify({'success': False,
                        'error': 'Gagal disconnect: ' + str(e)}), 500
    return jsonify({'success': True, 'data': result,
                    'message': 'Hardware dilepas. Program lain boleh memakai kamera/sensor.'})


@api_bp.route('/hardware/weight', methods=['GET'])
@api_login_required
def hardware_weight():
    """Baca berat loadcell saat ini (gram) untuk polling autopilot.

    connected=False jika sesi belum aktif (hardware belum di-Connect).
    """
    try:
        from web.measurement_engine import get_current_weight
        weight = get_current_weight()
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    if weight is None:
        return jsonify({'success': True,
                        'data': {'connected': False, 'weight_g': None}})
    return jsonify({'success': True,
                    'data': {'connected': True, 'weight_g': round(weight, 1)}})

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
@api_login_required
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
@api_login_required
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
