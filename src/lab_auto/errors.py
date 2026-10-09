class LabAutomationError(Exception):
    """Base error for recoverable lab automation failures."""


class ConfigError(LabAutomationError):
    """Configuration is missing, invalid, or internally inconsistent."""


class DeviceError(LabAutomationError):
    """Hardware adapter or raw binding operation failed."""


class HardwareBusyError(DeviceError):
    """Another operation still owns the hardware, including after an HTTP timeout."""


class SafetyError(LabAutomationError):
    """Requested action violates a configured safety rule."""


class WorkflowCancelled(LabAutomationError):
    """A running workflow observed a cancellation request at a checkpoint.

    Raised cooperatively so the workflow's normal failure path runs (forcing the
    laser off) before it unwinds. Subclasses ``LabAutomationError`` so ``except
    Exception`` safety handlers still catch it.
    """
