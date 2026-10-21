"""Windows窗口图标使用Unicode路径；原ICO及打包图标保持。"""

import ctypes
import sys
from ctypes import wintypes

from panda3d.core import GraphicsWindow

from ui import theme


def load_window_icon(window):
    if sys.platform != 'win32' or not isinstance(window, GraphicsWindow):
        return None
    # Panda当前Windows图标入口用窄字符LoadImage，中文安装路径须走W版本。
    user32 = ctypes.WinDLL('user32', use_last_error=True)
    user32.LoadImageW.argtypes = (wintypes.HINSTANCE, wintypes.LPCWSTR, wintypes.UINT,
                                 ctypes.c_int, ctypes.c_int, wintypes.UINT)
    user32.LoadImageW.restype = wintypes.HANDLE
    user32.PostMessageW.argtypes = (wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
    user32.PostMessageW.restype = wintypes.BOOL
    user32.DestroyIcon.argtypes = (wintypes.HANDLE,)
    user32.DestroyIcon.restype = wintypes.BOOL
    path = theme.asset_filename('coastal-drive.ico').toOsSpecific()
    handle = user32.LoadImageW(None, path, 1, 0, 0, 0x10 | 0x40)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    hwnd = window.getWindowHandle().getIntHandle()
    for size in (0, 1):
        # /Draw窗口线程须先回到消息泵；启动中同步SendMessage会互等。
        if not user32.PostMessageW(hwnd, 0x80, size, handle):
            error = ctypes.get_last_error()
            user32.DestroyIcon(handle)
            raise ctypes.WinError(error)
    return user32, handle


def release_window_icon(icon):
    if icon is not None:
        user32, handle = icon
        if not user32.DestroyIcon(handle):
            raise ctypes.WinError(ctypes.get_last_error())
