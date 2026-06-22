"""
CameraService - pemilik TUNGGAL cv2.VideoCapture (USB webcam V4L2).

Desain final (disetujui):

    CameraService.get_instance(opener)
            | owns
            v
       cv2.VideoCapture        <- opener me-reuse open_fixed_camera()
            | grab thread -> latest_frame + frame_id
       +----+----------------------+
       v                          v
    Preview (MJPEG)        MeasurementSession (kamera di-inject)

Satu thread background yang membaca kamera (cap.read() TIDAK thread-safe,
jadi hanya thread ini yang memanggilnya). Konsumen lain (preview & sesi
pengukuran) hanya menyalin frame terbaru di bawah lock pendek -> tidak ada
yang memegang lock kamera selama pengukuran panjang.

opener di-inject (callable -> (cap, device, width, height)) supaya modul HAL
ini tetap import-able di laptop tanpa hardware: pemanggil (measurement_engine)
yang menyediakan open_fixed_camera dari program-python.
"""

import threading
import time


class CameraService:
    """Singleton pemilik kamera dengan satu grab thread."""

    _instance = None
    _instance_lock = threading.Lock()

    def __init__(self, opener):
        # opener: callable() -> (cap, device, width, height); cap None bila gagal.
        self._opener = opener
        self._cap = None
        self._device = None
        self._width = 0
        self._height = 0
        self._frame = None
        self._frame_id = 0
        self._lock = threading.Lock()
        self._running = False
        self._thread = None
        self._viewers = 0

    # -----------------------------------------------------------------
    # Singleton accessors
    # -----------------------------------------------------------------
    @classmethod
    def get_instance(cls, opener=None):
        """Ambil/buat singleton. opener WAJIB pada pemanggilan pertama."""
        with cls._instance_lock:
            if cls._instance is None:
                if opener is None:
                    raise RuntimeError(
                        "CameraService belum diinisialisasi: opener wajib "
                        "diberikan pada pemanggilan pertama."
                    )
                cls._instance = cls(opener)
            return cls._instance

    @classmethod
    def peek_instance(cls):
        """Kembalikan singleton bila sudah ada, tanpa membuat baru."""
        with cls._instance_lock:
            return cls._instance

    # -----------------------------------------------------------------
    # Lifecycle
    # -----------------------------------------------------------------
    def start(self):
        """Buka kamera + mulai grab thread. Idempotent.

        Tolak start bila tahap18 (CLI legacy) sedang pegang kamera --
        kebijakan tahap18 sebagai pemilik tunggal saat aktif.
        """
        with self._lock:
            if self._running:
                return
            try:
                from web.camera_lock import ensure_web_can_use_camera, CameraBusyError
                ok, msg, pids = ensure_web_can_use_camera()
                if not ok:
                    raise CameraBusyError(msg, pids=pids)
            except ImportError:
                # camera_lock belum tersedia di lingkungan ini -- lanjut
                pass
            cap, device, width, height = self._opener()
            if cap is None:
                raise RuntimeError("Kamera gagal dibuka (CameraService).")
            self._cap = cap
            self._device = device
            self._width = int(width or 0)
            self._height = int(height or 0)
            self._frame = None
            self._running = True
            self._thread = threading.Thread(
                target=self._grab_loop, name="camera-grab", daemon=True
            )
            self._thread.start()

    def _grab_loop(self):
        """Satu-satunya pemanggil cap.read(). Simpan frame terbaru + id."""
        while True:
            with self._lock:
                running = self._running
                cap = self._cap
            if not running or cap is None:
                break
            ok, frame = cap.read()
            if not ok or frame is None:
                time.sleep(0.01)
                continue
            with self._lock:
                self._frame = frame
                self._frame_id += 1

    def stop(self):
        """Hentikan grab thread lalu release kamera. Aman dipanggil berulang.

        Urutan penting: set running=False -> join thread (tunggu cap.read()
        terakhir selesai) -> baru release cap. Mencegah release saat dibaca.
        """
        with self._lock:
            self._running = False
            thread = self._thread
            self._thread = None
        if thread is not None:
            thread.join(timeout=1.0)
        with self._lock:
            if self._cap is not None:
                try:
                    self._cap.release()
                except Exception:
                    pass
            self._cap = None
            self._frame = None

    # -----------------------------------------------------------------
    # Readers (dipakai preview & MeasurementSession)
    # -----------------------------------------------------------------
    def read(self):
        """Salinan frame BGR terbaru, atau None."""
        with self._lock:
            return None if self._frame is None else self._frame.copy()

    def read_with_id(self):
        """(frame_copy, frame_id). frame None bila belum ada frame.

        frame_id dipakai pemanggil untuk menghindari memproses frame yang
        sama dua kali (proteksi duplicate-frame pada deteksi kestabilan).
        """
        with self._lock:
            if self._frame is None:
                return None, self._frame_id
            return self._frame.copy(), self._frame_id

    def get_jpeg(self, quality=70):
        """Encode frame terbaru jadi bytes JPEG (untuk MJPEG). None bila kosong."""
        import cv2

        with self._lock:
            frame = None if self._frame is None else self._frame.copy()
        if frame is None:
            return None
        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
        return buf.tobytes() if ok else None

    def frame_size(self):
        with self._lock:
            return self._width, self._height

    def is_running(self):
        with self._lock:
            return self._running

    # -----------------------------------------------------------------
    # Viewer ref-count (preview lifecycle) — bukan policy, hanya bookkeeping
    # -----------------------------------------------------------------
    def add_viewer(self):
        with self._lock:
            self._viewers += 1
            return self._viewers

    def remove_viewer(self):
        with self._lock:
            if self._viewers > 0:
                self._viewers -= 1
            return self._viewers

    def viewer_count(self):
        with self._lock:
            return self._viewers

    def release_if_idle(self):
        """Lepas kamera bila tak ada viewer & sesi pengukuran tak aktif (agar tahap18 standalone bisa pakai /dev/video0)."""
        from web.measurement_engine import is_session_active
        with self._lock:
            if self._viewers > 0:
                return False
        if is_session_active():
            return False
        self.stop()
        return True
