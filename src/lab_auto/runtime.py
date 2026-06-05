from enum import Enum

from lab_auto.errors import ConfigError


class RuntimeMode(str, Enum):
    DRY_RUN = "dry_run"
    SIMULATED = "simulated"
    REAL = "real"


def parse_runtime_mode(value: str | RuntimeMode | None) -> RuntimeMode:
    if value is None:
        return RuntimeMode.DRY_RUN
    if isinstance(value, RuntimeMode):
        return value
    try:
        return RuntimeMode(value)
    except ValueError as exc:
        allowed = ", ".join(mode.value for mode in RuntimeMode)
        raise ConfigError(f"runtime.mode must be one of: {allowed}") from exc


def resolve_runtime_mode(
    configured: str | RuntimeMode | None,
    *,
    cli_real: bool = False,
    cli_dry_run: bool = False,
    cli_simulated: bool = False,
) -> RuntimeMode:
    selected = [cli_real, cli_dry_run, cli_simulated]
    if sum(bool(flag) for flag in selected) > 1:
        raise ConfigError("--real, --dry-run, and --simulated are mutually exclusive")
    if cli_real:
        return RuntimeMode.REAL
    if cli_dry_run:
        return RuntimeMode.DRY_RUN
    if cli_simulated:
        return RuntimeMode.SIMULATED
    mode = parse_runtime_mode(configured)
    if mode is RuntimeMode.REAL:
        raise ConfigError("runtime.mode=real requires --real")
    return mode
