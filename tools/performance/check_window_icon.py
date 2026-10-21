"""真实/Draw窗口验证中文路径图标与关闭；不测性能。"""

import argparse
import ctypes
import json
import sys
import time
from ctypes import wintypes
from pathlib import Path
from threading import Thread

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'src'))

from direct.showbase.ShowBase import ShowBase
from panda3d.core import loadPrcFileData

from ui.window_icon import load_window_icon, release_window_icon


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    loadPrcFileData('icon-check', 'audio-library-name null\nthreading-model /Draw\n'
                   'win-size 320 200\nwindow-title CoastalDrive Icon Check\nicon-filename\n')
    app = ShowBase()
    icon = load_window_icon(app.win)
    try:
        for _ in range(8):
            app.taskMgr.step()
        app.graphicsEngine.syncFrame()
        user32, handle = icon
        user32.SendMessageTimeoutW.argtypes = (wintypes.HWND, wintypes.UINT, wintypes.WPARAM,
            wintypes.LPARAM, wintypes.UINT, wintypes.UINT, ctypes.POINTER(ctypes.c_size_t))
        user32.SendMessageTimeoutW.restype = wintypes.LPARAM
        hwnd = app.win.getWindowHandle().getIntHandle()
        replies = []

        def query():
            for size in (0, 1):
                value = ctypes.c_size_t()
                ok = user32.SendMessageTimeoutW(hwnd, 0x7f, size, 0, 2, 1000, ctypes.byref(value))
                replies.append((bool(ok), value.value))

        # 查询也不能阻塞主窗口的任务泵；副线程读取，主线程继续正常绘制。
        reader = Thread(target=query)
        reader.start()
        deadline = time.perf_counter()+3
        while reader.is_alive() and time.perf_counter() < deadline:
            app.taskMgr.step()
        reader.join(3.)
        assert replies == [(True, handle), (True, handle)]
    finally:
        app.destroy()
        release_window_icon(icon)
    (args.output/'summary.json').write_text(json.dumps({'passed': True, 'pipeline': '/Draw',
        'small_and_large_icon_match': True, 'released_after_window_destroy': True}), encoding='utf-8')


if __name__ == '__main__':
    main()
