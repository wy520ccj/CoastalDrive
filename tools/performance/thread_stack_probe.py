"""自有Windows诊断进程的原生线程地址栈；采样运行不作性能通过依据。"""

import ctypes
from ctypes import wintypes
from pathlib import Path


def load_probe(path):
    probe = ctypes.WinDLL(str(path.resolve()), use_last_error=True)
    probe.capture_thread_stack.argtypes = (wintypes.DWORD, ctypes.POINTER(ctypes.c_ulonglong), wintypes.DWORD)
    probe.capture_thread_stack.restype = wintypes.DWORD
    return probe


def capture(probe, thread_id):
    frames = (ctypes.c_ulonglong*48)()
    count = probe.capture_thread_stack(thread_id, frames, len(frames))
    error = ctypes.get_last_error()
    if not count:
        raise ctypes.WinError(ctypes.get_last_error())
    # 线程已恢复后再查询模块名，不在挂起窗口线程时取得加载器锁。
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetModuleHandleExW.argtypes = (wintypes.DWORD, ctypes.c_void_p, ctypes.POINTER(wintypes.HMODULE))
    kernel.GetModuleFileNameW.argtypes = (wintypes.HMODULE, wintypes.LPWSTR, wintypes.DWORD)
    result = []
    for address in frames[:count]:
        module = wintypes.HMODULE()
        if kernel.GetModuleHandleExW(6, address, ctypes.byref(module)):
            name = ctypes.create_unicode_buffer(32768)
            if not kernel.GetModuleFileNameW(module, name, len(name)):
                raise ctypes.WinError(ctypes.get_last_error())
            result.append({'module': Path(name.value).name, 'offset': hex(address-module.value)})
        else:
            result.append({'module': 'unmapped', 'address': hex(address)})
    return {'frames': result, 'unwind_error': error}
