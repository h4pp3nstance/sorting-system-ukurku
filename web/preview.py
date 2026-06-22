"""
Live Camera Preview - MJPEG.

Saat box mengukur (tahap18), kamera dipegang tahap18 yang menulis frame
ber-anotasi (kotak deteksi + ukuran + status) ke /dev/shm; preview
menyajikan frame itu. Saat box idle, preview memakai CameraService
(pemilik kamera web). Auto-switch per frame berdasarkan kesegaran file
annotated, jadi operator tak perlu RDP ke monitor Pi.
"""

import os
import time

from flask import Blueprint, Response, jsonify

from web.auth import role_required, ROLE_MITRA, ROLE_MPC, ROLE_ADMIN

preview_bp = Blueprint('preview', __name__)

_FPS = int(os.getenv("PREVIEW_FPS", "30"))
_QUALITY = int(os.getenv("PREVIEW_JPEG_QUALITY", "70"))
_ANNOTATED_FILE = "/dev/shm/ukurku_live_annotated.jpg"
_ANNOTATED_FRESH_SEC = 2.0


def _read_annotated_fresh():
    """JPEG annotated dari /dev/shm bila ada & segar (<2s), else None."""
    try:
        if os.path.getmtime(_ANNOTATED_FILE) < time.time() - _ANNOTATED_FRESH_SEC:
            return None
        with open(_ANNOTATED_FILE, "rb") as f:
            return f.read()
    except OSError:
        return None


@preview_bp.route('/video_feed')
@role_required(ROLE_MITRA, ROLE_MPC, ROLE_ADMIN)
def video_feed():
    from web.measurement_engine import get_camera_service

    def generate():
        target_dt = 1.0 / _FPS if _FPS > 0 else 0
        cam = None
        viewer_added = False
        try:
            while True:
                t0 = time.time()

                # Prioritas: frame annotated tahap18 (box sedang mengukur).
                jpeg = _read_annotated_fresh()

                if jpeg is None:
                    # Box idle -> pakai CameraService (pemilik kamera web).
                    if cam is None:
                        try:
                            cam = get_camera_service()
                            cam.start()
                            cam.add_viewer()
                            viewer_added = True
                        except Exception:
                            cam = None
                    if cam is not None and cam.is_running():
                        jpeg = cam.get_jpeg(quality=_QUALITY)
                elif cam is not None and viewer_added:
                    # tahap18 ambil alih kamera -> lepas CameraService.
                    cam.remove_viewer()
                    cam.release_if_idle()
                    viewer_added = False
                    cam = None

                if jpeg is not None:
                    yield (b"--frame\r\n"
                           b"Content-Type: image/jpeg\r\n"
                           b"Content-Length: " + str(len(jpeg)).encode() +
                           b"\r\n\r\n" + jpeg + b"\r\n")
                dt = time.time() - t0
                if target_dt and dt < target_dt:
                    time.sleep(target_dt - dt)
        finally:
            if cam is not None and viewer_added:
                cam.remove_viewer()
                cam.release_if_idle()

    return Response(
        generate(),
        mimetype="multipart/x-mixed-replace; boundary=frame",
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'}
    )
