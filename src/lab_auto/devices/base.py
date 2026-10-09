def close_all_quietly(devices) -> None:
    """Close every device exactly once; one failing ``close()`` must not stop the rest.

    Cleanup paths must release every handle even if one ``close()`` raises —
    stopping on the first failure leaks the rest and masks the real error.
    ``None`` entries (devices that were never opened) are skipped.
    """
    seen: set[int] = set()
    for device in devices:
        if device is None or id(device) in seen:
            continue
        seen.add(id(device))
        try:
            device.close()
        except Exception:  # noqa: BLE001 - cleanup must continue regardless
            pass
