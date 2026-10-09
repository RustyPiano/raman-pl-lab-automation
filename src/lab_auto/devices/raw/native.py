import ctypes
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LoadedLibrary:
    lib: object
    # 保留 add_dll_directory 返回的句柄，句柄释放后依赖 DLL 的搜索路径会失效
    dll_directory_handle: object | None = None

    def __getattr__(self, name: str):
        return getattr(self.lib, name)


def load_library(dll_path: Path) -> LoadedLibrary:
    dll_path = Path(dll_path)
    dll_directory_handle = None
    if hasattr(os, "add_dll_directory"):
        dll_directory_handle = os.add_dll_directory(str(dll_path.parent))
    lib = ctypes.WinDLL(str(dll_path)) if hasattr(ctypes, "WinDLL") else ctypes.CDLL(str(dll_path))
    return LoadedLibrary(lib=lib, dll_directory_handle=dll_directory_handle)


def maybe_configure(lib, name: str, argtypes, restype) -> None:
    # 可选导出函数不存在时跳过；必需导出由 has_required_exports 先检查
    func = getattr(lib, name, None)
    if func is not None:
        func.argtypes = argtypes
        func.restype = restype
