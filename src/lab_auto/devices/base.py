from typing import Protocol


class Device(Protocol):
    def close(self) -> None:
        ...


def close_all_quietly(devices) -> None:
    """Best-effort close every device exactly once; never stop on a close failure.

    Cleanup paths must release every handle even if one ``close()`` raises —
    stopping on the first failure leaks the rest and masks the real error. Each
    unique device (dedup by identity) is closed in its own try/except.
    """
    seen: set[int] = set()
    for device in devices:
        if device is None or id(device) in seen:
            continue
        seen.add(id(device))
        close = getattr(device, "close", None)
        if close is None:
            continue
        try:
            close()
        except Exception:  # noqa: BLE001 - cleanup must continue regardless
            pass
