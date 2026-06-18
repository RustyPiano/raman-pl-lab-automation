import platform
from pathlib import Path

from lab_auto.config import DevicesConfig, WorkflowConfig
from lab_auto.devices.dfield_camera import DFieldCamera
from lab_auto.devices.light import PWM_MODBUS_READ_TIMEOUT_S, ManualLight, PwmModbusLight
from lab_auto.devices.light_safety import validate_pwm_light_config
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
from lab_auto.workflow.raman import RamanWorkflow
from lab_auto.workflow.tray_scan import TrayScanWorkflow


def _path_exists(path: Path) -> bool:
    return Path(path).exists()


def _scan_to_workflow_config(scan_config) -> WorkflowConfig:
    """Adapt the per-point fields of a tray-scan config to a single-point config."""
    return WorkflowConfig(
        devices_config=scan_config.devices_config,
        sample=scan_config.sample,
        optics=scan_config.optics,
        acquisition=scan_config.acquisition,
        output=scan_config.output,
    )


def _unwired_mask_provider(wafer):
    raise DeviceError(
        "tray-scan mask provider is not wired: inject a recognition hook "
        "(camera capture + sample recognition) via create_tray_scan_workflow(mask_provider=...)"
    )


class RamanPointMeasurer:
    """Per-point measurement primitive backed by the single-point Raman workflow.

    Each call runs one single-point acquisition and returns its sample
    intensities so the tray-scan workflow can burn-check the repeats.
    """

    def __init__(self, raman: "RamanWorkflow"):
        self.raman = raman

    def measure_point(self, *, point_id, x_um, y_um, role, repeat, require_confirmation):
        import csv
        from types import SimpleNamespace

        run_dir = self.raman.run_single_point(require_confirmation=require_confirmation)
        intensities: list[float] = []
        with (run_dir / "raw.csv").open(encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                intensities.append(float(row["intensity_raw"]))
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
        return {
            "python_64bit": platform.architecture()[0] == "64bit",
            "stage_port": devices_config.stage.port,
            "zolix_dll_exists": _path_exists(zolix_dll),
            "zolix_ftd2xx_exists": _path_exists(zolix_dll.parent / "ftd2xx.dll"),
            "zolix_loadable": self._can_load_zolix(zolix_dll) if _path_exists(zolix_dll) else False,
            "dfield_dll_exists": _path_exists(dfield_dll),
            "dfield_loadable": self._can_load_dfield(dfield_dll) if _path_exists(dfield_dll) else False,
        }

    def run_scan(self, devices_config: DevicesConfig) -> dict:
        serial_ports = []
        try:
            from serial.tools import list_ports

            serial_ports = [port.device for port in list_ports.comports()]
        except ImportError:
            serial_ports = []
        waynelabs = {"configured_port": devices_config.stage.port, "device": None}
        if devices_config.stage.port in serial_ports:
            stage = None
            try:
                stage = self.create_stage(devices_config)
                waynelabs["device"] = stage.identify()
            except DeviceError as exc:
                waynelabs["error"] = str(exc)
            finally:
                if stage is not None:
                    stage.close()
        zolix_devices: list[str] = []
        if _path_exists(devices_config.spectrometer.dll_path):
            try:
                loaded = load_zolix_library(devices_config.spectrometer.dll_path)
                if has_required_zolix_exports(loaded):
                    configure_zolix_signatures(loaded)
                    raw = ZolixRawClient(loaded)
                    raw.set_usb_mode(devices_config.spectrometer.usb_mode)
                    zolix_devices = raw.enumerate_serial_numbers()
            except OSError:
                zolix_devices = []
        return {
            "runtime_mode": devices_config.runtime.mode.value,
            "serial_ports": serial_ports,
            "configured_stage_port": devices_config.stage.port,
            "waynelabs": waynelabs,
            "zolix_devices": zolix_devices,
            "dfield_available": self._can_load_dfield(devices_config.camera.dll_path) if _path_exists(devices_config.camera.dll_path) else False,
        }

    def run_status(self, devices_config: DevicesConfig) -> dict:
        return {
            "runtime_mode": devices_config.runtime.mode.value,
            "scan": self.run_scan(devices_config),
            "doctor": self.run_doctor(devices_config),
        }

    def create_stage(self, devices_config: DevicesConfig) -> WaynelabsStage:
        try:
            import serial
        except ImportError as exc:
            raise DeviceError("pyserial is required for real WayneLabs stage control") from exc
        try:
            transport = serial.Serial(
                port=devices_config.stage.port,
                baudrate=devices_config.stage.baudrate,
                timeout=WAYNELABS_SERIAL_READ_TIMEOUT_S,
                write_timeout=2,
            )
        except Exception as exc:
            raise DeviceError(f"failed to open WayneLabs stage serial port {devices_config.stage.port}: {exc}") from exc
        return WaynelabsStage(devices_config.stage, transport=transport, dry_run=False, ledger=PositionLedger.load(devices_config.stage))

    def create_spectrometer(self, devices_config: DevicesConfig) -> ZolixSpectrometer:
        try:
            loaded = load_zolix_library(devices_config.spectrometer.dll_path)
            if not has_required_zolix_exports(loaded):
                raise DeviceError("Zolix DLL is missing required Phase 1 exports")
            configure_zolix_signatures(loaded)
            raw = ZolixRawClient(loaded)
            raw.set_usb_mode(devices_config.spectrometer.usb_mode)
            device_id = raw.open_first_device()
            return ZolixSpectrometer(raw, device_id=device_id)
        except DeviceError:
            raise
        except (OSError, AttributeError) as exc:
            raise DeviceError(f"failed to create Zolix spectrometer: {exc}") from exc

    def create_camera(self, devices_config: DevicesConfig) -> DFieldCamera:
        try:
            loaded = load_dfield_library(devices_config.camera.dll_path)
            if not has_required_dfield_exports(loaded):
                raise DeviceError("DField DLL is missing required Phase 1 exports")
            configure_dfield_signatures(loaded)
            return DFieldCamera(DFieldRawClient(loaded))
        except DeviceError:
            raise
        except (OSError, AttributeError) as exc:
            raise DeviceError(f"failed to create DField camera: {exc}") from exc

    def create_light(self, devices_config: DevicesConfig):
        light_config = devices_config.light
        if light_config.type == "manual":
            if not light_config.manual_light_control:
                raise DeviceError("Phase 1 real workflow requires manual_light_control=true")
            return ManualLight(manual=True)
        if light_config.type == "pwm_modbus":
            validate_pwm_light_config(light_config)
            transport = self._open_pwm_transport(light_config)
            return PwmModbusLight(light_config, transport=transport, dry_run=False)
        raise DeviceError(f"unsupported light type: {light_config.type}")

    def _open_pwm_transport(self, light_config):
        try:
            import serial
        except ImportError as exc:
            raise DeviceError("pyserial is required for real PWM light control") from exc
        try:
            return serial.Serial(
                port=light_config.port,
                baudrate=light_config.baudrate,
                timeout=PWM_MODBUS_READ_TIMEOUT_S,
                write_timeout=2,
            )
        except Exception as exc:
            raise DeviceError(f"failed to open PWM light serial port {light_config.port}: {exc}") from exc

    def create_tray_scan_workflow(self, scan_config, devices_config: DevicesConfig, *, mask_provider=None):
        """Compose a real tray-scan workflow.

        The per-point measurement reuses the single-point Raman primitive; the
        ``mask_provider`` (camera capture + recognition) is injected by the
        recognition integration and is required for a real run.
        """
        light = self.create_light(devices_config)
        stage = None
        spectrometer = None
        camera = None
        try:
            stage = self.create_stage(devices_config)
            spectrometer = self.create_spectrometer(devices_config)
            camera = self.create_camera(devices_config)
            workflow_config = _scan_to_workflow_config(scan_config)
            raman = RamanWorkflow.real(workflow_config, stage=stage, spectrometer=spectrometer, camera=camera, light=light)
            measurer = RamanPointMeasurer(raman)
            provider = mask_provider if mask_provider is not None else _unwired_mask_provider
            return TrayScanWorkflow.real(scan_config, stage=stage, point_measurer=measurer, mask_provider=provider)
        except Exception:
            for device in (camera, spectrometer, stage, light):
                if device is not None:
                    close = getattr(device, "close", None)
                    if close is not None:
                        close()
            raise

    def create_single_point_workflow(self, workflow_config: WorkflowConfig, devices_config: DevicesConfig):
        light = self.create_light(devices_config)
        stage = None
        spectrometer = None
        camera = None
        try:
            stage = self.create_stage(devices_config)
            spectrometer = self.create_spectrometer(devices_config)
            camera = self.create_camera(devices_config)
            return RamanWorkflow.real(
                workflow_config,
                stage=stage,
                spectrometer=spectrometer,
                camera=camera,
                light=light,
            )
        except Exception:
            for device in (camera, spectrometer, stage, light):
                if device is not None:
                    close = getattr(device, "close", None)
                    if close is not None:
                        close()
            raise
