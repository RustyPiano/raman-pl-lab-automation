"""Minimal nncam (toupcam-family) still capture for wafer imaging.

One RGB frame per wafer, saved to a file, to hand to the recognition program.
Reuses the vendor's ``nncam.py`` binding (lazy-imported, so the core stays
torch/SDK-free); the native lib (``nncam.dll``/``.so``/``.dylib``) must sit
beside it on the lab machine. Capture-only — no live preview.

Hardware-verify knobs (can't be validated without the real camera):
``upside_down`` (image orientation) and exposure. Byte order is forced to RGB
so Pillow reads channels correctly; tight row packing (``rowPitch=-1``) avoids
DIB 4-byte alignment padding for odd widths.
"""

import ctypes
import sys
import threading
from pathlib import Path

from lab_auto.errors import DeviceError

_FRAME_TIMEOUT_S = 10.0


def _rgb24_tight_bufsize(width: int, height: int) -> int:
    """Tightly packed RGB24 buffer size (rowPitch=-1): 3 bytes/pixel, no padding."""
    return width * 3 * height


def _load_nncam(sdk_python_dir):
    if sdk_python_dir is not None and str(sdk_python_dir) not in sys.path:
        sys.path.insert(0, str(sdk_python_dir))  # dir holding nncam.py + native lib
    try:
        import nncam
    except ImportError as exc:  # pragma: no cover - environment-dependent
        raise DeviceError(
            "nncam binding not importable; put the SDK's python/ dir on the path "
            "(sdk_python_dir=) with the native nncam lib beside it"
        ) from exc
    return nncam


class NncamImager:
    """Open once, ``snap_to_file`` per wafer, ``close`` at end."""

    def __init__(self, hcam, nncam, width: int, height: int, *, settle_frames: int = 2):
        self._hcam = hcam
        self._nncam = nncam
        self.width = width
        self.height = height
        self._settle = settle_frames
        # A writable ctypes char array is the correct pull buffer: PullImageV3 has no
        # ctypes argtype, so it writes into the buffer's memory in place. (A Python
        # `bytes` "works" but mutating it is UB, and crucially `bytes(bytes_obj)` is
        # NOT a copy — it returns the same object — so a bytes snapshot would alias
        # the live buffer.) `bytes(ctypes_array)` DOES copy, giving a real snapshot.
        self._buf = (ctypes.c_char * _rgb24_tight_bufsize(width, height))()
        self._lock = threading.Lock()
        self._snap = None  # latest fully-pulled frame, an independent immutable copy
        self._frame = threading.Event()
        hcam.StartPullModeWithCallback(self._on_event, self)

    @classmethod
    def open(cls, *, sdk_python_dir=None, index: int = 0, exposure_ms=None, upside_down: int = 0, settle_frames: int = 2):
        nncam = _load_nncam(sdk_python_dir)
        devices = nncam.Nncam.EnumV2()
        if not devices:
            raise DeviceError("no nncam camera found")
        if index >= len(devices):
            raise DeviceError(f"nncam index {index} out of range ({len(devices)} found)")
        hcam = nncam.Nncam.Open(devices[index].id)
        if hcam is None:
            raise DeviceError("failed to open nncam camera")
        try:
            hcam.put_Option(nncam.NNCAM_OPTION_BYTEORDER, 0)  # 0 => RGB (Pillow-correct)
            hcam.put_Option(nncam.NNCAM_OPTION_UPSIDE_DOWN, upside_down)  # hardware-verify knob
            if exposure_ms is None:
                hcam.put_AutoExpoEnable(1)
            else:
                hcam.put_AutoExpoEnable(0)
                hcam.put_ExpoTime(int(exposure_ms * 1000))  # nncam expo time is microseconds
            width, height = hcam.get_Size()
            return cls(hcam, nncam, width, height, settle_frames=settle_frames)
        except Exception as exc:
            hcam.Close()
            raise DeviceError(f"failed to configure nncam camera: {exc}") from exc

    # callback fires on the SDK's internal thread; pull under the lock and publish
    # an immutable snapshot so snap_to_file never reads a half-overwritten buffer.
    @staticmethod
    def _on_event(event, self):
        if event != self._nncam.NNCAM_EVENT_IMAGE:
            return
        with self._lock:
            hcam = self._hcam
            if hcam is None:  # closed mid-stream — don't touch a freed SDK handle
                return
            try:
                hcam.PullImageV3(self._buf, 0, 24, -1, None)  # bits=24, rowPitch=-1 (tight)
            except self._nncam.HRESULTException:
                return  # drop a bad pull; snap_to_file's wait will retry/time out
            self._snap = bytes(self._buf)  # snapshot read safely by snap_to_file
        self._frame.set()

    def snap_to_file(self, path):
        """Grab a fresh, exposure-settled frame and save it (format from the suffix)."""
        from PIL import Image  # lazy: only the inference/lab machine needs it

        # Discard self._settle frames so continuous auto-exposure has converged,
        # then take the next. ponytail: a frame-count warmup, not a true
        # NNCAM_EVENT_AUTOEXPO_CONV wait — switch to the convergence event if a
        # fixed warmup proves unreliable on the real camera.
        snap = None
        for _ in range(self._settle + 1):
            self._frame.clear()  # ignore the in-flight frame; wait for a fresh capture
            if not self._frame.wait(timeout=_FRAME_TIMEOUT_S):
                raise DeviceError("timed out waiting for an nncam frame")
            with self._lock:
                snap = self._snap
        if snap is None:  # pragma: no cover - frame set but snapshot missing
            raise DeviceError("no nncam frame captured")
        img = Image.frombytes("RGB", (self.width, self.height), snap)
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        img.save(path)
        return path

    def close(self):
        with self._lock:  # publish None so an in-flight callback bails out
            hcam = self._hcam
            self._hcam = None
        if hcam is not None:
            hcam.Close()


def demo():
    assert _rgb24_tight_bufsize(4, 2) == 24, _rgb24_tight_bufsize(4, 2)
    assert _rgb24_tight_bufsize(3, 3) == 27, _rgb24_tight_bufsize(3, 3)  # odd width, no padding
    print("nncam_camera bufsize ok")


if __name__ == "__main__":
    demo()
