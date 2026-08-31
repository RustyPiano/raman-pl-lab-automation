from dataclasses import replace
from pathlib import Path

import pytest

from lab_auto.cli import main
from lab_auto.config import load_devices_config, load_workflow_config
from lab_auto.devices.factory import DeviceFactory
from lab_auto.errors import ConfigError, DeviceError, SafetyError


def write_devices_config(path: Path):
    path.write_text(
        """
runtime: {mode: real, log_level: info}
stage:
  type: waynelabs_linear
  port: COM5
  baudrate: 9600
  resolution_um: {x: 0.04, y: 0.04, z: 0.04}
  default_speed: 8
  soft_limits_um: {x: [-5000, 5000], y: [-5000, 5000], z: [-1000, 1000]}
  state_file: state/stage_position.json
  max_unknown_move_um: 100
spectrometer: {type: zolix, dll_path: C:/SDK/spectrometer_x64.dll, usb_mode: true}
camera: {type: dfield_vs_a4, dll_path: C:/SDK/dfield-vs-a4.dll}
light: {type: manual, manual_light_control: true}
""",
        encoding="utf-8",
    )


def test_devices_doctor_real_uses_factory(tmp_path: Path):
    devices = tmp_path / "devices.real.yaml"
    write_devices_config(devices)
    factory = FakeDeviceFactory()

    exit_code = main(["devices", "doctor", "--config", str(devices), "--real"], factory=factory)

    assert exit_code == 0
    assert factory.calls == [("run_doctor", "COM5")]


def test_devices_scan_and_status_real_use_factory(tmp_path: Path):
    devices = tmp_path / "devices.real.yaml"
    write_devices_config(devices)
    factory = FakeDeviceFactory()

    assert main(["devices", "scan", "--config", str(devices), "--real"], factory=factory) == 0
    assert main(["devices", "status", "--config", str(devices), "--real"], factory=factory) == 0

    assert factory.calls == [("run_scan", "COM5"), ("run_status", "COM5")]


def test_devices_scan_real_uses_effective_runtime_override(tmp_path: Path):
    devices = tmp_path / "devices.yaml"
    write_devices_config(devices)
    text = devices.read_text(encoding="utf-8").replace("runtime: {mode: real, log_level: info}", "runtime: {mode: dry_run, log_level: info}")
    devices.write_text(text, encoding="utf-8")
    factory = FakeDeviceFactory()

    assert main(["devices", "scan", "--config", str(devices), "--real"], factory=factory) == 0

    assert factory.modes == ["real"]


def test_real_config_without_real_flag_does_not_touch_hardware_factory(tmp_path: Path, capsys):
    devices = tmp_path / "devices.real.yaml"
    write_devices_config(devices)
    factory = FakeDeviceFactory()

    exit_code = main(["stage", "identify", "--config", str(devices)], factory=factory)

    assert exit_code == 2
    assert factory.stage.calls == []
    assert "requires --real" in capsys.readouterr().out


def test_stage_identify_and_home_real_use_factory_adapter(tmp_path: Path):
    devices = tmp_path / "devices.real.yaml"
    write_devices_config(devices)
    factory = FakeDeviceFactory()

    assert main(["stage", "identify", "--config", str(devices), "--real"], factory=factory) == 0
    assert main(
        ["stage", "home", "--config", str(devices), "--real", "--axis", "x", "--direction", "negative", "--speed", "8", "--yes"],
        factory=factory,
    ) == 0

    assert factory.stage.calls == [("identify",), ("home", "x", "negative", 8)]


def test_stage_move_real_uses_factory_adapter(tmp_path: Path, capsys):
    devices = tmp_path / "devices.real.yaml"
    write_devices_config(devices)
    factory = FakeDeviceFactory()

    exit_code = main(
        ["stage", "move", "--config", str(devices), "--real", "--axis", "x", "--um", "10", "--speed", "8", "--yes"],
        factory=factory,
    )

    assert exit_code == 0
    assert factory.stage.calls == [("move_relative", "x", 10.0, 8)]
    assert "stage_move_complete" in capsys.readouterr().out


def test_stage_move_real_safety_error_returns_recoverable_cli_failure(tmp_path: Path, capsys):
    devices = tmp_path / "devices.real.yaml"
    write_devices_config(devices)
    factory = FakeDeviceFactory()
    factory.stage.raise_safety = True

    exit_code = main(
        ["stage", "move", "--config", str(devices), "--real", "--axis", "x", "--um", "10", "--speed", "8", "--yes"],
        factory=factory,
    )

    assert exit_code == 2
    assert "soft limit" in capsys.readouterr().out


def test_stage_move_real_invalid_axis_fails_before_opening_stage(tmp_path: Path, capsys):
    devices = tmp_path / "devices.real.yaml"
    write_devices_config(devices)
    factory = FakeDeviceFactory()

    exit_code = main(
        ["stage", "move", "--config", str(devices), "--real", "--axis", "q", "--um", "10", "--speed", "8", "--yes"],
        factory=factory,
    )

    assert exit_code == 2
    assert factory.stage.calls == []
    assert "unsupported stage axis" in capsys.readouterr().out


def test_real_hardware_construction_os_error_returns_recoverable_cli_failure(tmp_path: Path, capsys):
    devices = tmp_path / "devices.real.yaml"
    write_devices_config(devices)

    exit_code = main(["stage", "identify", "--config", str(devices), "--real"], factory=RawErrorFactory())

    assert exit_code == 2
    assert "serial failed" in capsys.readouterr().out


def test_spec_status_and_init_real_use_factory_adapter(tmp_path: Path):
    devices = tmp_path / "devices.real.yaml"
    write_devices_config(devices)
    factory = FakeDeviceFactory()

    assert main(["spec", "status", "--config", str(devices), "--real"], factory=factory) == 0
    assert main(["spec", "init", "--config", str(devices), "--real", "--entrance", "side", "--exit", "direct"], factory=factory) == 0

    assert factory.spectrometer.calls == [
        ("status",),
        ("initialize", "side", "direct"),
    ]


def test_spec_init_real_invalid_port_fails_before_opening_spectrometer(tmp_path: Path, capsys):
    devices = tmp_path / "devices.real.yaml"
    write_devices_config(devices)
    factory = FakeDeviceFactory()

    exit_code = main(["spec", "init", "--config", str(devices), "--real", "--entrance", "bogus", "--exit", "direct"], factory=factory)

    assert exit_code == 2
    assert factory.spectrometer.calls == []
    assert "unsupported Zolix port" in capsys.readouterr().out


def test_spec_set_real_uses_factory_adapter(tmp_path: Path):
    devices = tmp_path / "devices.real.yaml"
    write_devices_config(devices)
    factory = FakeDeviceFactory()

    exit_code = main(
        ["spec", "set", "--config", str(devices), "--real", "--grating", "1", "--wavelength-nm", "600", "--slit-um", "100"],
        factory=factory,
    )

    assert exit_code == 0
    assert factory.spectrometer.calls == [
        ("set_grating", 1),
        ("move_to_wavelength_nm", 600.0),
        ("set_slit_width_um", 100),
    ]


def test_spec_set_real_invalid_optics_fails_before_opening_spectrometer(tmp_path: Path, capsys):
    devices = tmp_path / "devices.real.yaml"
    write_devices_config(devices)
    factory = FakeDeviceFactory()

    exit_code = main(
        ["spec", "set", "--config", str(devices), "--real", "--grating", "1", "--wavelength-nm", "-1", "--slit-um", "-5"],
        factory=factory,
    )

    assert exit_code == 2
    assert factory.spectrometer.calls == []
    assert "wavelength" in capsys.readouterr().out


def test_camera_status_real_uses_factory_adapter(tmp_path: Path):
    devices = tmp_path / "devices.real.yaml"
    write_devices_config(devices)
    factory = FakeDeviceFactory()

    exit_code = main(["camera", "status", "--config", str(devices), "--real"], factory=factory)

    assert exit_code == 0
    assert factory.camera.calls == [("status",)]


def test_camera_capture_real_uses_factory_adapter(tmp_path: Path):
    devices = tmp_path / "devices.real.yaml"
    out = tmp_path / "capture.csv"
    write_devices_config(devices)
    factory = FakeDeviceFactory()

    exit_code = main(
        ["camera", "capture", "--config", str(devices), "--real", "--mode", "fvb", "--exposure-ms", "1000", "--gain", "low", "--out", str(out)],
        factory=factory,
    )

    assert exit_code == 0
    assert factory.camera.calls == [("capture_to_csv", "fvb", 1000.0, "low", out)]


def test_camera_capture_real_malformed_roi_fails_before_opening_camera(tmp_path: Path, capsys):
    devices = tmp_path / "devices.real.yaml"
    write_devices_config(devices)
    factory = FakeDeviceFactory()

    exit_code = main(
        [
            "camera",
            "capture",
            "--config",
            str(devices),
            "--real",
            "--mode",
            "image",
            "--exposure-ms",
            "1000",
            "--gain",
            "low",
            "--out",
            str(tmp_path / "capture.csv"),
            "--roi",
            "a,b,c,d",
        ],
        factory=factory,
    )

    assert exit_code == 2
    assert factory.camera.calls == []
    assert "--roi" in capsys.readouterr().out


def test_camera_temperature_real_uses_factory_adapter(tmp_path: Path):
    devices = tmp_path / "devices.real.yaml"
    write_devices_config(devices)
    factory = FakeDeviceFactory()

    exit_code = main(["camera", "temperature", "--config", str(devices), "--real"], factory=factory)

    assert exit_code == 0
    assert factory.camera.calls == [("temperature_c",)]


def test_stage_trigger_real_uses_factory_adapter(tmp_path: Path):
    devices = tmp_path / "devices.real.yaml"
    write_devices_config(devices)
    factory = FakeDeviceFactory()

    exit_code = main(["stage", "trigger", "--config", str(devices), "--real", "--mode", "open-loop", "--yes"], factory=factory)

    assert exit_code == 0
    assert factory.stage.calls == [("trigger", "open_loop")]


def test_factory_closes_stage_if_spectrometer_creation_fails():
    factory = PartiallyFailingFactory()

    with pytest.raises(DeviceError, match="spectrometer failed"):
        factory.create_single_point_workflow(
            workflow_config=load_workflow_config("configs/single_point.example.yaml"),
            devices_config=None,
        )

    assert factory.stage.closed is True


def test_config_rejects_manual_light_without_confirmation(tmp_path: Path):
    devices = tmp_path / "devices.real.yaml"
    write_devices_config(devices)
    devices.write_text(devices.read_text(encoding="utf-8").replace("manual_light_control: true", "manual_light_control: false"), encoding="utf-8")

    with pytest.raises(ConfigError, match="manual_light_control=true"):
        load_devices_config(devices)


def test_factory_validates_workflow_before_opening_devices():
    workflow = load_workflow_config("configs/single_point.example.yaml")
    workflow = replace(
        workflow,
        acquisition=replace(workflow.acquisition, exposure_ms=60_001),
    )
    factory = LightSafetyFactory()

    with pytest.raises(ConfigError, match="safety cap"):
        factory.create_single_point_workflow(workflow, devices_config=None)

    assert factory.calls == []


def test_dry_run_diagnostics_do_not_load_vendor_libraries(tmp_path):
    config = load_devices_config("configs/devices.example.yaml")
    zolix = tmp_path / "zolix.dll"
    dfield = tmp_path / "dfield.dll"
    zolix.touch()
    dfield.touch()
    config = replace(
        config,
        spectrometer=replace(config.spectrometer, dll_path=zolix),
        camera=replace(config.camera, dll_path=dfield),
    )

    class NoProbeFactory(DeviceFactory):
        def _can_load_zolix(self, dll_path):
            raise AssertionError("dry-run must not load the Zolix DLL")

        def _can_load_dfield(self, dll_path):
            raise AssertionError("dry-run must not load the DField DLL")

    factory = NoProbeFactory()

    assert factory.run_doctor(config)["zolix_loadable"] is False
    assert factory.run_scan(config)["dfield_available"] is False


class FakeDeviceFactory:
    def __init__(self):
        self.calls = []
        self.modes = []
        self.stage = FakeStage()
        self.spectrometer = FakeSpectrometer()
        self.camera = FakeCamera()

    def run_doctor(self, devices_config):
        self.calls.append(("run_doctor", devices_config.stage.port))
        return {"python_64bit": True}

    def run_scan(self, devices_config):
        self.calls.append(("run_scan", devices_config.stage.port))
        self.modes.append(devices_config.runtime.mode.value)
        return {"runtime_mode": devices_config.runtime.mode.value}

    def run_status(self, devices_config):
        self.calls.append(("run_status", devices_config.stage.port))
        self.modes.append(devices_config.runtime.mode.value)
        return {"runtime_mode": devices_config.runtime.mode.value}

    def create_stage(self, devices_config):
        return self.stage

    def create_spectrometer(self, devices_config):
        return self.spectrometer

    def create_camera(self, devices_config):
        return self.camera


class FakeStage:
    def __init__(self):
        self.calls = []
        self.raise_safety = False

    def identify(self):
        self.calls.append(("identify",))
        return {"type": "waynelabs_linear", "port": "COM5"}

    def home(self, *, axis: str, direction: str, speed: int):
        self.calls.append(("home", axis, direction, speed))

    def move_relative(self, *, axis: str, um: float, speed: int):
        if self.raise_safety:
            raise SafetyError("soft limit")
        self.calls.append(("move_relative", axis, um, speed))

    def trigger(self, *, mode: str):
        self.calls.append(("trigger", mode))

    def close(self):
        pass


class FakeSpectrometer:
    def __init__(self):
        self.calls = []

    def status(self):
        self.calls.append(("status",))
        return {"device_id": 7}

    def initialize(self, *, entrance_port: str, exit_port: str):
        self.calls.append(("initialize", entrance_port, exit_port))

    def set_grating(self, grating: int):
        self.calls.append(("set_grating", grating))

    def move_to_wavelength_nm(self, wavelength_nm: float):
        self.calls.append(("move_to_wavelength_nm", wavelength_nm))

    def set_slit_width_um(self, width_um: int):
        self.calls.append(("set_slit_width_um", width_um))

    def close(self):
        pass


class FakeCamera:
    def __init__(self):
        self.calls = []

    def status(self):
        self.calls.append(("status",))
        return {"open": True}

    def capture_to_csv(self, *, mode: str, exposure_ms: float, gain: str, out: Path):
        self.calls.append(("capture_to_csv", mode, exposure_ms, gain, out))

    def temperature_c(self):
        self.calls.append(("temperature_c",))
        return 23.5

    def close(self):
        pass


class PartiallyFailingFactory(DeviceFactory):
    def __init__(self):
        self.stage = ClosableStage()

    def create_light(self, devices_config):
        return object()

    def create_stage(self, devices_config):
        return self.stage

    def create_spectrometer(self, devices_config):
        raise DeviceError("spectrometer failed")


class ClosableStage:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class LightSafetyFactory(DeviceFactory):
    def __init__(self):
        self.calls = []

    def create_stage(self, devices_config):
        self.calls.append("stage")
        raise AssertionError("stage should not open before light safety validation")


class RawErrorFactory(FakeDeviceFactory):
    def create_stage(self, devices_config):
        raise OSError("serial failed")


PWM_LIGHT_BLOCK = """light:
  type: pwm_modbus
  manual_light_control: false
  port: COM7
  station_id: 3
  baudrate: 9600
  max_output_voltage_v: 5.0
  required_output_voltage_v: 5.0
  channels:
    led: {channel: 1, frequency_hz: 1000, duty_percent: 5.0, default_off_required: true}
    laser: {channel: 2, frequency_hz: 1000, duty_percent: 5.0, default_off_required: true}
"""


def write_pwm_devices_config(path: Path):
    write_devices_config(path)
    text = path.read_text(encoding="utf-8").replace(
        "light: {type: manual, manual_light_control: true}\n", PWM_LIGHT_BLOCK
    )
    path.write_text(text, encoding="utf-8")


def test_create_light_returns_manual_light_for_manual_type(tmp_path: Path):
    devices = tmp_path / "devices.real.yaml"
    write_devices_config(devices)
    from lab_auto.devices.light import ManualLight

    light = DeviceFactory().create_light(load_devices_config(devices))
    assert isinstance(light, ManualLight)


class PwmSerialFactory(DeviceFactory):
    """Override the serial seam so tests need no real pyserial port."""

    def __init__(self):
        self.opened = {}

    def _open_pwm_transport(self, light_config):
        self.opened["port"] = light_config.port
        self.opened["baudrate"] = light_config.baudrate
        return object()


def test_create_light_dispatches_pwm_modbus_backend(tmp_path: Path):
    devices = tmp_path / "devices.real.yaml"
    write_pwm_devices_config(devices)
    config = load_devices_config(devices)
    factory = PwmSerialFactory()

    from lab_auto.devices.light import PwmModbusLight

    # initial_all_off=False: this seam returns a dummy transport, so skip the
    # power-on reset and only assert backend dispatch.
    light = factory.create_light(config, initial_all_off=False)
    assert isinstance(light, PwmModbusLight)
    assert light.station == 3
    assert light.config.channels["laser"].channel == 2
    assert factory.opened == {"port": "COM7", "baudrate": 9600}


class _RecordingModbusSlave:
    """Minimal correct Modbus RTU slave over write()/read(n) that logs requests."""

    def __init__(self, *, station, registers=None, ignore_writes_to=()):
        self.station = station
        self.registers = dict(registers or {})
        self.ignore_writes_to = set(ignore_writes_to)
        self.requests = []
        self.closed = False
        self._out = bytearray()

    def write(self, data: bytes) -> None:
        from lab_auto.devices.raw import pwm_modbus as mb

        self.requests.append(bytes(data))
        station, func = data[0], data[1]
        if func == mb.READ:
            addr = (data[2] << 8) | data[3]
            count = (data[4] << 8) | data[5]
            body = bytes([station, func, count * 2])
            for offset in range(count):
                reg = self.registers.get(addr + offset, 0)
                body += bytes([(reg >> 8) & 0xFF, reg & 0xFF])
            self._out += body + mb.crc16(body)
        elif func == mb.WRITE_SINGLE:
            addr = (data[2] << 8) | data[3]
            value = (data[4] << 8) | data[5]
            if addr not in self.ignore_writes_to:
                self.registers[addr] = value
            self._out += bytes(data)  # echo

    def read(self, n: int) -> bytes:
        chunk = bytes(self._out[:n])
        del self._out[:n]
        return chunk

    def close(self) -> None:
        self.closed = True


class PwmResetFactory(DeviceFactory):
    """Override the serial seam with an in-memory modbus slave (no pyserial)."""

    def __init__(self, slave):
        self.slave = slave

    def _open_pwm_transport(self, light_config):
        return self.slave


def test_create_light_runs_power_on_all_off_before_returning(tmp_path: Path):
    from lab_auto.devices.light import PwmModbusLight
    from lab_auto.devices.raw import pwm_modbus as mb

    devices = tmp_path / "devices.real.yaml"
    write_pwm_devices_config(devices)
    config = load_devices_config(devices)
    slave = _RecordingModbusSlave(station=config.light.station_id)
    factory = PwmResetFactory(slave)

    light = factory.create_light(config)

    assert isinstance(light, PwmModbusLight)
    writes = [f for f in slave.requests if f[1] == mb.WRITE_SINGLE]
    off_regs = {(f[2] << 8) | f[3] for f in writes}
    assert off_regs == {mb.output_state_register(ch) for ch in (1, 2, 3, 4, 5)}
    for f in writes:  # every power-on write drove a channel OFF
        assert ((f[4] << 8) | f[5]) == 0
    # write-then-read-back ordering for channel 1
    reg1 = mb.output_state_register(1)
    idx_write = next(i for i, f in enumerate(slave.requests) if f[1] == mb.WRITE_SINGLE and ((f[2] << 8) | f[3]) == reg1)
    idx_read = next(i for i, f in enumerate(slave.requests) if f[1] == mb.READ and ((f[2] << 8) | f[3]) == reg1)
    assert idx_write < idx_read


def test_create_light_raises_and_closes_when_power_on_reset_cannot_confirm_off(tmp_path: Path):
    from lab_auto.devices.raw import pwm_modbus as mb

    devices = tmp_path / "devices.real.yaml"
    write_pwm_devices_config(devices)
    config = load_devices_config(devices)
    laser_reg = mb.output_state_register(2)  # laser channel from PWM_LIGHT_BLOCK
    slave = _RecordingModbusSlave(
        station=config.light.station_id,
        registers={laser_reg: 1},  # laser stuck energized
        ignore_writes_to={laser_reg},  # off write never takes
    )
    factory = PwmResetFactory(slave)

    with pytest.raises(DeviceError, match="safety reset"):
        factory.create_light(config)
    assert slave.closed is True


def test_create_light_skips_power_on_reset_when_disabled(tmp_path: Path):
    from lab_auto.devices.raw import pwm_modbus as mb

    devices = tmp_path / "devices.real.yaml"
    write_pwm_devices_config(devices)
    config = load_devices_config(devices)
    slave = _RecordingModbusSlave(station=config.light.station_id)
    factory = PwmResetFactory(slave)

    factory.create_light(config, initial_all_off=False)

    assert not [f for f in slave.requests if f[1] == mb.WRITE_SINGLE]
