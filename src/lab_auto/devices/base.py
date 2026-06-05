from typing import Protocol


class Device(Protocol):
    def close(self) -> None:
        ...
