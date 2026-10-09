import csv
import platform
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace

import serial
from serial.tools import list_ports

from lab_auto.config import DevicesConfig, WorkflowConfig, workflow_config_from_tray_scan
from lab_auto.devices.base import close_all_quietly
from lab_auto.devices.dfield_camera import DFieldCamera
from lab_auto.devices.light import PWM_MODBUS_READ_TIMEOUT_S, ManualLight, PwmModbusLight
from lab_auto.devices.raw.dfield_ctypes import (
    DFieldRawClient,
    configure_signatures as configure_dfield_signatures,
    has_required_exports as has_required_dfield_exports,
    load_library as load_dfield_library,
)
from lab_auto.devices.raw.zolix_ctypes import (
    ZolixRawClient,
    configure_signatures as configure_zolix_signatures,
    has_required_exports as has_required_zolix_exports,
    load_library as load_zolix_library,
)
from lab_auto.devices.waynelabs_stage import WAYNELABS_SERIAL_READ_TIMEOUT_S, PositionLedger, WaynelabsStage
from lab_auto.devices.zolix_spectrometer import ZolixSpectrometer
from lab_auto.errors import DeviceError
from lab_auto.runtime import RuntimeMode
from lab_auto.workflow.raman import RamanWorkflow
from lab_auto.workflow.tray_scan import TrayScanWorkflow


class RamanPointMeasurer:
    """Per-point measurement primitive backed by the single-point Raman workflow.

    Each call runs one single-point acquisition and returns its sample
    intensities so the tray-scan workflow can burn-check the repeats.
    """

    def __init__(self, raman: "RamanWorkflow"):
        self.raman = raman

    def measure_point(
        self, *, point_id, x_um, y_um, role, repeat, require_confirmation, should_cancel=None
    ):
        run_dir = self.raman.run_single_point(
            require_confirmation=require_confirmation,
            should_cancel=should_cancel,
        )
        corrected = self.raman.config.acquisition.subtract_background
        filename = "corrected.csv" if corrected else "raw.csv"
        column = "intensity_corrected" if corrected else "intensity_raw"
        intensities: list[float] = []
        with (run_dir / filename).open(encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                if any(row.get(key, "false").lower() == "true" for key in ("saturated", "saturated_raw", "saturated_background")):
                    raise DeviceError("burn check cannot classify saturated spectra")
                intensities.append(float(row[column]))
        return SimpleNamespace(intensities=intensities, output_path=str(run_dir))

    def close(self) -> None:
        self.raman.close()


class DeviceFactory:
    def _can_load_zolix(self, dll_path: Path) -> bool:
        try:
            loaded = load_zolix_library(dll_path)
            if not has_required_zolix_exports(loaded):
                return False
            configure_zolix_signatures(loaded)
            ZolixRawClient(loaded).get_status(device_id=0)
            return True
        except (OSError, AttributeError):
            return False

    def _can_load_dfield(self, dll_path: Path) -> bool:
        try:
            loaded = load_dfield_library(dll_path)
            if not has_required_dfield_exports(loaded):
                return False
            configure_dfield_signatures(loaded)
            return True
        except (OSError, AttributeError):
            return False

    def run_doctor(self, devices_config: DevicesConfig) -> dict:
        zolix_dll = devices_config.spectrometer.dll_path
        dfield_dll = devices_config.camera.dll_path
        probe_hardware = devices_config.runtime.mode is RuntimeMode.REAL
        return {
            "python_64bit": platform.architecture()[0] == "64bit",
            "stage_port": devices_config.stage.port,
            "zolix_dll_exists": zolix_dll.exists(),
            "zolix_ftd2xx_exists": (zolix_dll.parent / "ftd2xx.dll").exists(),
            "zolix_loadable": probe_hardware and zolix_dll.exists() and self._can_load_zolix(zolix_dll),
            "dfield_dll_exists": dfield_dll.exists(),
            "dfield_loadable": probe_hardware and dfield_dll.exists() and self._can_load_dfield(dfield_dll),
        }

    def run_scan(self, devices_config: DevicesConfig) -> dict:
        real = devices_config.runtime.mode is RuntimeMode.REAL
        serial_ports = [port.device for port in list_ports.comports()]
        waynelabs = {"configured_port": devices_config.stage.port, "device": None}
        if real and devices_config.stage.port in serial_ports:
            stage = None
            try:
                stage = self.create_stage(devices_config)
                waynelabs["device"] = stage.identify()
            except DeviceError as exc:
                waynelabs["error"] = str(exc)
            finally:
                if stage is not None:
                    stage.close()
        zolix_dll = devices_config.spectrometer.dll_path
        dfield_dll = devices_config.camera.dll_path
        zolix_devices: list[str] = []
        if real and zolix_dll.exists():
            loaded = load_zolix_library(zolix_dll)
            if has_required_zolix_exports(loaded):
                configure_zolix_signatures(loaded)
                raw = ZolixRawClient(loaded)
                raw.set_usb_mode(devices_config.spectrometer.usb_mode)
                zolix_devices = raw.enumerate_serial_numbers()
        return {
            "runtime_mode": devices_config.runtime.mode.value,
            "serial_ports": serial_ports,
            "configured_stage_port": devices_config.stage.port,
            "waynelabs": waynelabs,
            "zolix_devices": zolix_devices,
            "dfield_available": real and dfield_dll.exists() and self._can_load_dfield(dfield_dll),
        }

    def run_status(self, devices_config: DevicesConfig) -> dict:
        return {
            "runtime_mode": devices_config.runtime.mode.value,
            "scan": self.run_scan(devices_config),
            "doctor": self.run_doctor(devices_config),
        }

    def create_stage(self, devices_config: DevicesConfig) -> WaynelabsStage:
        try:
            transport = serial.Serial(
                port=devices_config.stage.port,
                baudrate=devices_config.stage.baudrate,
                timeout=WAYNELABS_SERIAL_READ_TIMEOUT_S,
                write_timeout=2,
            )
        except serial.SerialException as exc:
            raise DeviceError(f"failed to open WayneLabs stage serial port {devices_config.stage.port}: {exc}") from exc
        return WaynelabsStage(devices_config.stage, transport=transport, dry_run=False, ledger=PositionLedger.load(devices_config.stage))

    def create_spectrometer(self, devices_config: DevicesConfig) -> ZolixSpectrometer:
        try:
            loaded = load_zolix_library(devices_config.spectrometer.dll_path)
        except OSError as exc:
            raise DeviceError(f"failed to create Zolix spectrometer: {exc}") from exc
        if not has_required_zolix_exports(loaded):
            raise DeviceError("Zolix DLL is missing required exports")
        configure_zolix_signatures(loaded)
        raw = ZolixRawClient(loaded)
        raw.set_usb_mode(devices_config.spectrometer.usb_mode)
        return ZolixSpectrometer(raw, device_id=raw.open_first_device())

    def create_camera(self, devices_config: DevicesConfig) -> DFieldCamera:
        try:
            loaded = load_dfield_library(devices_config.camera.dll_path)
        except OSError as exc:
            raise DeviceError(f"failed to create DField camera: {exc}") from exc
        if not has_required_dfield_exports(loaded):
            raise DeviceError("DField DLL is missing required exports")
        configure_dfield_signatures(loaded)
        return DFieldCamera(DFieldRawClient(loaded))

    def create_light(self, devices_config: DevicesConfig, *, initial_all_off: bool = True):
        light_config = devices_config.light
        if light_config.type == "manual":
            return ManualLight()
        light = PwmModbusLight(light_config, transport=self._open_pwm_transport(light_config))
        if initial_all_off:
            # Power-on safety: a crash may have left a channel (possibly the
            # laser) energized. Force every channel off with read-back before
            # handing the device out. Read-only status paths pass False.
            try:
                light.safety_reset()
            except Exception:
                light.close(all_off=False)  # already tried off; just drop the port
                raise
        return light

    def _open_pwm_transport(self, light_config):
        try:
            return serial.Serial(
                port=light_config.port,
                baudrate=light_config.baudrate,
                timeout=PWM_MODBUS_READ_TIMEOUT_S,
                write_timeout=2,
            )
        except serial.SerialException as exc:
            raise DeviceError(f"failed to open PWM light serial port {light_config.port}: {exc}") from exc

    def _create_raman_workflow(self, workflow_config: WorkflowConfig, devices_config: DevicesConfig) -> RamanWorkflow:
        RamanWorkflow.dry_run(workflow_config).validate_single_point_config()
        light = self.create_light(devices_config)
        stage = spectrometer = camera = None
        try:
            stage = self.create_stage(devices_config)
            spectrometer = self.create_spectrometer(devices_config)
            camera = self.create_camera(devices_config)
        except Exception:
            close_all_quietly((camera, spectrometer, stage, light))
            raise
        workflow = RamanWorkflow.real(workflow_config, stage=stage, spectrometer=spectrometer, camera=camera, light=light)
        workflow.devices_snapshot = asdict(devices_config)
        return workflow

    def create_tray_scan_workflow(self, scan_config, devices_config: DevicesConfig, *, mask_provider):
        """Compose a real tray-scan workflow.

        The per-point measurement reuses the single-point Raman primitive;
        ``mask_provider`` is the recognition file handshake.
        """
        raman = self._create_raman_workflow(workflow_config_from_tray_scan(scan_config), devices_config)
        return TrayScanWorkflow.real(
            scan_config, stage=raman.stage, point_measurer=RamanPointMeasurer(raman), mask_provider=mask_provider
        )

    def create_single_point_workflow(self, workflow_config: WorkflowConfig, devices_config: DevicesConfig):
        return self._create_raman_workflow(workflow_config, devices_config)
