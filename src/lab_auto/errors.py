class LabAutomationError(Exception):
    """Base error for recoverable lab automation failures."""


class ConfigError(LabAutomationError):
    """Configuration is missing, invalid, or internally inconsistent."""


class DeviceError(LabAutomationError):
    """Hardware adapter or raw binding operation failed."""


class SafetyError(LabAutomationError):
    """Requested action violates a configured safety rule."""
