import csv
from pathlib import Path

from lab_auto.devices.dfield_validation import validate_dfield_bin_roi, validate_dfield_capture_args
from lab_auto.devices.optics_validation import validate_zolix_optics
from lab_auto.errors import ConfigError
from lab_auto.workflow.data import CaptureFrame
from lab_auto.devices.zolix_spectrometer import direct_to_front_bool


class SimulatedCamera:
    def status(self) -> dict:
        return {"type": "simulated", "open": True, "width": 2048, "height": 1}

    def capture(
        self,
        *,
        read_mode: str,
        exposure_ms: float,
        gain: str,
        frames: int,
        bin_x: int = 1,
        bin_y: int = 1,
        roi: tuple[int, int, int, int] | None = None,
    ) -> CaptureFrame:
        validate_dfield_capture_args(
            read_mode=read_mode,
            exposure_ms=exposure_ms,
            gain=gain,
            frames=frames,
            bin_x=bin_x,
            bin_y=bin_y,
            roi=roi,
        )
        if read_mode == "fvb":
            detector_width = 2048
            detector_height = 1
            width = detector_width // bin_x
            height = 1
        elif read_mode == "image":
            detector_width = 16
            detector_height = 8
            validate_dfield_bin_roi(bin_x=bin_x, bin_y=bin_y, roi=roi, detector_width=detector_width, detector_height=detector_height)
            if roi is None:
                roi_width = detector_width
                roi_height = detector_height
            else:
                roi_width = roi[1] - roi[0] + 1
                roi_height = roi[3] - roi[2] + 1
            width = roi_width // bin_x
            height = roi_height // bin_y
        else:
            raise ConfigError(f"unsupported DField read_mode: {read_mode}")
        values = [1000 + index for index in range(width * height)]
        if width <= 0 or height <= 0:
            raise ConfigError("simulated capture dimensions must be positive")
        return CaptureFrame(
            read_mode=read_mode,
            width=width,
            height=height,
            bin_x=bin_x,
            bin_y=bin_y,
            roi=roi,
            exposure_ms=exposure_ms,
            gain=gain,
            values=values,
            saturated_count=0,
            saturated=[False for _ in values],
            metadata={
                "read_mode": read_mode,
                "bin_x": bin_x,
                "bin_y": bin_y,
                "roi": roi,
                "detector_width": detector_width,
                "detector_height": detector_height,
                "raw_frames_count": frames,
                "saturation_threshold": 65535,
            },
            raw_frames_count=frames,
            saturation_threshold=65535,
        )

    def capture_to_csv(
        self,
        *,
        mode: str,
        exposure_ms: float,
        gain: str,
        out: Path,
        bin_x: int = 1,
        bin_y: int = 1,
        roi: tuple[int, int, int, int] | None = None,
    ) -> None:
        frame = self.capture(read_mode=mode, exposure_ms=exposure_ms, gain=gain, frames=1, bin_x=bin_x, bin_y=bin_y, roi=roi)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            if mode == "image":
                writer.writerow(["row", "col", "intensity_raw", "saturated"])
                for index, (value, saturated) in enumerate(zip(frame.values, frame.saturated, strict=True)):
                    row, col = divmod(index, frame.width)
                    writer.writerow([row, col, value, str(saturated).lower()])
            else:
                writer.writerow(["pixel_index", "intensity_raw", "saturated"])
                for index, (value, saturated) in enumerate(zip(frame.values, frame.saturated, strict=True)):
                    writer.writerow([index, value, str(saturated).lower()])

    def temperature_c(self) -> float:
        return 23.5


class SimulatedSpectrometer:
    def __init__(self):
        self.grating = 1
        self.current_wavelength_nm = 600.0
        self.slit_width_um = 100
        self.entrance_port = "side"
        self.exit_port = "direct"

    def status(self) -> dict:
        return {
            "type": "simulated",
            "serial_number": "simulated",
            "dll_version": None,
            "entrance_port": self.entrance_port,
            "exit_port": self.exit_port,
            "grating": self.grating,
            "current_wavelength_nm": self.current_wavelength_nm,
            "slit_width_um": self.slit_width_um,
        }

    def initialize(self, *, entrance_port: str, exit_port: str) -> bool:
        direct_to_front_bool(entrance_port)
        direct_to_front_bool(exit_port)
        self.entrance_port = entrance_port
        self.exit_port = exit_port
        return True

    def set_grating(self, grating: int) -> bool:
        validate_zolix_optics(grating=grating)
        self.grating = grating
        return True

    def move_to_wavelength_nm(self, wavelength_nm: float) -> bool:
        validate_zolix_optics(wavelength_nm=wavelength_nm)
        self.current_wavelength_nm = wavelength_nm
        return True

    def set_slit_width_um(self, width_um: int) -> bool:
        validate_zolix_optics(slit_um=width_um)
        self.slit_width_um = width_um
        return True

    def pixels_to_waves(self, *, turret: int, grating: int, center_wavelength_nm: float, width: int, count: int, bin_x: int) -> list[float]:
        middle = (count - 1) / 2
        return [round(center_wavelength_nm + (index - middle) * 0.01, 6) for index in range(count)]

    def close(self) -> None:
        pass
