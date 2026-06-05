import argparse
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path

from lab_auto.config import RuntimeConfig, load_devices_config, load_workflow_and_devices
from lab_auto.devices.dfield_validation import validate_dfield_capture_args
from lab_auto.devices.factory import DeviceFactory
from lab_auto.devices.optics_validation import validate_zolix_optics
from lab_auto.devices.simulated import SimulatedCamera, SimulatedSpectrometer
from lab_auto.devices.waynelabs_stage import PositionLedger, WaynelabsStage
from lab_auto.devices.zolix_spectrometer import direct_to_front_bool
from lab_auto.errors import ConfigError, DeviceError, SafetyError
from lab_auto.runtime import RuntimeMode, resolve_runtime_mode
from lab_auto.workflow.raman import RamanWorkflow


def add_runtime_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--simulated", action="store_true")
    parser.add_argument("--real", action="store_true")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ramanctl")
    subparsers = parser.add_subparsers(dest="domain", required=True)

    devices = subparsers.add_parser("devices")
    devices_sub = devices.add_subparsers(dest="command", required=True)
    for command in ("scan", "status", "doctor"):
        item = devices_sub.add_parser(command)
        item.add_argument("--config")
        add_runtime_flags(item)

    stage = subparsers.add_parser("stage")
    stage_sub = stage.add_subparsers(dest="command", required=True)
    identify = stage_sub.add_parser("identify")
    identify.add_argument("--config", required=True)
    add_runtime_flags(identify)
    move = stage_sub.add_parser("move")
    move.add_argument("--config", required=True)
    move.add_argument("--axis", required=True)
    move.add_argument("--um", required=True, type=float)
    move.add_argument("--speed", required=True, type=int)
    move.add_argument("--yes", action="store_true")
    add_runtime_flags(move)
    home = stage_sub.add_parser("home")
    home.add_argument("--config", required=True)
    home.add_argument("--axis", required=True)
    home.add_argument("--direction", required=True)
    home.add_argument("--speed", required=True, type=int)
    home.add_argument("--yes", action="store_true")
    add_runtime_flags(home)
    trigger = stage_sub.add_parser("trigger")
    trigger.add_argument("--config", required=True)
    trigger.add_argument("--mode", required=True, choices=("open-loop", "closed-loop"))
    trigger.add_argument("--yes", action="store_true")
    add_runtime_flags(trigger)

    spec = subparsers.add_parser("spec")
    spec_sub = spec.add_subparsers(dest="command", required=True)
    spec_status = spec_sub.add_parser("status")
    spec_status.add_argument("--config", required=True)
    add_runtime_flags(spec_status)
    spec_init = spec_sub.add_parser("init")
    spec_init.add_argument("--config", required=True)
    spec_init.add_argument("--entrance", required=True)
    spec_init.add_argument("--exit", required=True)
    add_runtime_flags(spec_init)
    spec_set = spec_sub.add_parser("set")
    spec_set.add_argument("--config", required=True)
    spec_set.add_argument("--grating", required=True, type=int)
    spec_set.add_argument("--wavelength-nm", required=True, type=float)
    spec_set.add_argument("--slit-um", required=True, type=int)
    add_runtime_flags(spec_set)

    camera = subparsers.add_parser("camera")
    camera_sub = camera.add_subparsers(dest="command", required=True)
    camera_status = camera_sub.add_parser("status")
    camera_status.add_argument("--config", required=True)
    add_runtime_flags(camera_status)
    temperature = camera_sub.add_parser("temperature")
    temperature.add_argument("--config", required=True)
    add_runtime_flags(temperature)
    capture = camera_sub.add_parser("capture")
    capture.add_argument("--config", required=True)
    capture.add_argument("--mode", required=True)
    capture.add_argument("--exposure-ms", required=True, type=float)
    capture.add_argument("--gain", default="low")
    capture.add_argument("--out", required=True)
    capture.add_argument("--bin-x", default=1, type=int)
    capture.add_argument("--bin-y", default=1, type=int)
    capture.add_argument("--roi", help="col_from,col_to,row_from,row_to")
    add_runtime_flags(capture)

    workflow = subparsers.add_parser("workflow")
    workflow_sub = workflow.add_subparsers(dest="command", required=True)
    single = workflow_sub.add_parser("single")
    single.add_argument("--config", required=True)
    single.add_argument("--devices-config")
    single.add_argument("--yes", action="store_true")
    add_runtime_flags(single)
    return parser


def _resolve_devices_args_mode(args, devices_config):
    return resolve_runtime_mode(devices_config.runtime.mode, cli_real=args.real, cli_dry_run=args.dry_run, cli_simulated=args.simulated)


def _with_runtime_mode(devices_config, mode: RuntimeMode):
    return replace(devices_config, runtime=RuntimeConfig(mode=mode, log_level=devices_config.runtime.log_level))


def _print_dry_run(action: str) -> int:
    print(action)
    return 0


def _parse_roi(value: str | None) -> tuple[int, int, int, int] | None:
    if value is None:
        return None
    parts = [part.strip() for part in value.split(",")]
    if len(parts) != 4:
        raise ConfigError("--roi must be col_from,col_to,row_from,row_to")
    try:
        return tuple(int(part) for part in parts)
    except ValueError as exc:
        raise ConfigError("--roi must contain integer bounds") from exc


def _capture_kwargs(args) -> dict:
    kwargs = {"mode": args.mode, "exposure_ms": args.exposure_ms, "gain": args.gain, "out": Path(args.out)}
    roi = _parse_roi(args.roi)
    if args.bin_x != 1 or args.bin_y != 1 or roi is not None:
        kwargs.update({"bin_x": args.bin_x, "bin_y": args.bin_y, "roi": roi})
    return kwargs


def _run_real_hardware_command(args, devices_config, factory: DeviceFactory) -> int | None:
    if args.domain == "devices" and args.command == "scan":
        print(factory.run_scan(devices_config))
        return 0
    if args.domain == "devices" and args.command == "status":
        print(factory.run_status(devices_config))
        return 0
    if args.domain == "devices" and args.command == "doctor":
        print(factory.run_doctor(devices_config))
        return 0
    if args.domain == "stage" and args.command == "identify":
        stage = factory.create_stage(devices_config)
        try:
            print(stage.identify())
        finally:
            stage.close()
        return 0
    if args.domain == "stage" and args.command == "move":
        if not args.yes:
            raise ConfigError("real stage move requires --yes")
        stage = factory.create_stage(devices_config)
        try:
            stage.move_relative(axis=args.axis, um=args.um, speed=args.speed)
        finally:
            stage.close()
        print("stage_move_complete")
        return 0
    if args.domain == "stage" and args.command == "home":
        if not args.yes:
            raise ConfigError("real stage home requires --yes")
        stage = factory.create_stage(devices_config)
        try:
            stage.home(axis=args.axis, direction=args.direction, speed=args.speed)
        finally:
            stage.close()
        print("stage_home_complete")
        return 0
    if args.domain == "stage" and args.command == "trigger":
        if not args.yes:
            raise ConfigError("real stage trigger requires --yes")
        stage = factory.create_stage(devices_config)
        try:
            stage.trigger(mode=args.mode.replace("-", "_"))
        finally:
            stage.close()
        print("stage_trigger_complete")
        return 0
    if args.domain == "spec" and args.command == "status":
        spec = factory.create_spectrometer(devices_config)
        try:
            print(spec.status())
        finally:
            spec.close()
        return 0
    if args.domain == "spec" and args.command == "init":
        spec = factory.create_spectrometer(devices_config)
        try:
            spec.initialize(entrance_port=args.entrance, exit_port=args.exit)
        finally:
            spec.close()
        print("spec_init_complete")
        return 0
    if args.domain == "spec" and args.command == "set":
        spec = factory.create_spectrometer(devices_config)
        try:
            spec.set_grating(args.grating)
            spec.move_to_wavelength_nm(args.wavelength_nm)
            spec.set_slit_width_um(args.slit_um)
        finally:
            spec.close()
        print("spec_set_complete")
        return 0
    if args.domain == "camera" and args.command == "status":
        camera = factory.create_camera(devices_config)
        try:
            print(camera.status())
        finally:
            camera.close()
        return 0
    if args.domain == "camera" and args.command == "temperature":
        camera = factory.create_camera(devices_config)
        try:
            print(camera.temperature_c())
        finally:
            camera.close()
        return 0
    if args.domain == "camera" and args.command == "capture":
        camera = factory.create_camera(devices_config)
        try:
            camera.capture_to_csv(**_capture_kwargs(args))
        finally:
            camera.close()
        print("camera_capture_complete")
        return 0
    return None


def _simulated_stage(devices_config) -> WaynelabsStage:
    return WaynelabsStage(devices_config.stage, transport=None, dry_run=True, ledger=PositionLedger.load(devices_config.stage))


def _validate_capture_args(args) -> None:
    validate_dfield_capture_args(
        read_mode=args.mode,
        exposure_ms=args.exposure_ms,
        gain=args.gain,
        frames=1,
        bin_x=args.bin_x,
        bin_y=args.bin_y,
        roi=_parse_roi(args.roi),
    )


def _validate_real_hardware_args(args, devices_config) -> None:
    if args.domain == "stage":
        stage = _simulated_stage(devices_config)
        if args.command == "move":
            if not args.yes:
                raise ConfigError("real stage move requires --yes")
            stage.move_relative(axis=args.axis, um=args.um, speed=args.speed)
        elif args.command == "home":
            if not args.yes:
                raise ConfigError("real stage home requires --yes")
            stage.home(axis=args.axis, direction=args.direction, speed=args.speed)
        elif args.command == "trigger":
            if not args.yes:
                raise ConfigError("real stage trigger requires --yes")
            stage.trigger(mode=args.mode.replace("-", "_"))
    elif args.domain == "spec":
        if args.command == "init":
            direct_to_front_bool(args.entrance)
            direct_to_front_bool(args.exit)
        elif args.command == "set":
            validate_zolix_optics(grating=args.grating, wavelength_nm=args.wavelength_nm, slit_um=args.slit_um)
    elif args.domain == "camera" and args.command == "capture":
        _validate_capture_args(args)


def _run_non_real_hardware_command(args, devices_config, mode: RuntimeMode) -> int | None:
    simulated = mode is RuntimeMode.SIMULATED
    if args.domain == "stage":
        stage = _simulated_stage(devices_config)
        if args.command == "identify":
            print(stage.identify() if simulated else "stage_identify")
            return 0
        if args.command == "move":
            stage.move_relative(axis=args.axis, um=args.um, speed=args.speed)
            return _print_dry_run(f"stage_move:{args.axis}:{args.um}")
        if args.command == "home":
            stage.home(axis=args.axis, direction=args.direction, speed=args.speed)
            return _print_dry_run(f"stage_home:{args.axis}:{args.direction}")
        if args.command == "trigger":
            stage.trigger(mode=args.mode.replace("-", "_"))
            return _print_dry_run(f"stage_trigger:{args.mode}")
    if args.domain == "spec":
        spec = SimulatedSpectrometer()
        if args.command == "status":
            print(spec.status() if simulated else "spec_status")
            return 0
        if args.command == "init":
            spec.initialize(entrance_port=args.entrance, exit_port=args.exit)
            return _print_dry_run(f"spec_init:entrance={args.entrance}:exit={args.exit}")
        if args.command == "set":
            spec.set_grating(args.grating)
            spec.move_to_wavelength_nm(args.wavelength_nm)
            spec.set_slit_width_um(args.slit_um)
            return _print_dry_run(f"spec_set:grating={args.grating}:wavelength_nm={args.wavelength_nm}:slit_um={args.slit_um}")
    if args.domain == "camera":
        camera = SimulatedCamera()
        if args.command == "status":
            print(camera.status() if simulated else "camera_status")
            return 0
        if args.command == "temperature":
            print(camera.temperature_c() if simulated else "camera_temperature")
            return 0
        if args.command == "capture":
            _validate_capture_args(args)
            kwargs = _capture_kwargs(args)
            if simulated:
                camera.capture_to_csv(**kwargs)
                print("camera_capture_complete")
            else:
                camera.capture(read_mode=args.mode, exposure_ms=args.exposure_ms, gain=args.gain, frames=1, bin_x=args.bin_x, bin_y=args.bin_y, roi=_parse_roi(args.roi))
                print(f"camera_capture:mode={args.mode}:out={args.out}")
            return 0
    return None


def main(argv: Sequence[str] | None = None, *, factory: DeviceFactory | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    factory = factory or DeviceFactory()
    try:
        if args.domain == "workflow" and args.command == "single":
            workflow_config, devices_config = load_workflow_and_devices(args.config, devices_override=args.devices_config)
            mode = resolve_runtime_mode(devices_config.runtime.mode, cli_real=args.real, cli_dry_run=args.dry_run, cli_simulated=args.simulated)
            devices_config = _with_runtime_mode(devices_config, mode)
            RamanWorkflow.dry_run(workflow_config).validate_single_point_config()
            print(f"devices_config:{args.devices_config or workflow_config.devices_config}")
            if mode is RuntimeMode.REAL:
                workflow = factory.create_single_point_workflow(workflow_config, devices_config)
                try:
                    print(workflow.run_single_point(require_confirmation=not args.yes))
                finally:
                    workflow.close()
                return 0
            workflow = RamanWorkflow.dry_run(workflow_config) if mode is RuntimeMode.DRY_RUN else RamanWorkflow.simulated(workflow_config)
            if mode is RuntimeMode.DRY_RUN:
                for action in workflow.measure_single_point(require_confirmation=not args.yes):
                    print(action)
            else:
                print(workflow.run_single_point(require_confirmation=not args.yes))
            return 0

        devices_config = load_devices_config(args.config) if getattr(args, "config", None) else None
        if args.domain == "devices" and args.real and devices_config is None:
            raise ConfigError("devices --real requires --config")
        mode = _resolve_devices_args_mode(args, devices_config) if devices_config is not None else RuntimeMode.DRY_RUN
        if devices_config is not None:
            devices_config = _with_runtime_mode(devices_config, mode)
        if mode is RuntimeMode.REAL:
            _validate_real_hardware_args(args, devices_config)
            result = _run_real_hardware_command(args, devices_config, factory)
            if result is not None:
                return result
        if devices_config is not None:
            result = _run_non_real_hardware_command(args, devices_config, mode)
            if result is not None:
                return result

        if args.domain == "devices":
            return _print_dry_run(f"devices_{args.command}")
        if args.domain == "stage":
            if args.command == "identify":
                return _print_dry_run("stage_identify")
            if args.command == "move":
                return _print_dry_run(f"stage_move:{args.axis}:{args.um}")
            if args.command == "home":
                return _print_dry_run(f"stage_home:{args.axis}:{args.direction}")
            if args.command == "trigger":
                return _print_dry_run(f"stage_trigger:{args.mode}")
        if args.domain == "spec":
            if args.command == "status":
                return _print_dry_run("spec_status")
            if args.command == "init":
                return _print_dry_run(f"spec_init:entrance={args.entrance}:exit={args.exit}")
            if args.command == "set":
                return _print_dry_run(f"spec_set:grating={args.grating}:wavelength_nm={args.wavelength_nm}:slit_um={args.slit_um}")
        if args.domain == "camera":
            if args.command == "status":
                return _print_dry_run("camera_status")
            if args.command == "temperature":
                return _print_dry_run("camera_temperature")
            if args.command == "capture":
                return _print_dry_run(f"camera_capture:mode={args.mode}:out={args.out}")
    except (ConfigError, DeviceError, SafetyError, OSError, AttributeError) as exc:
        print(f"error: {exc}")
        return 2
    parser.error("unsupported command")
