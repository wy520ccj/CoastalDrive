"""启动时间线的轻量记录；只在显式测量时创建。"""

import time


class StartupTrace:
    def __init__(self, process_start_ns=None, *, clock_ns=time.perf_counter_ns):
        self.clock_ns = clock_ns
        self.events = []
        self.closed = False
        if process_start_ns is not None:
            self.events.append(("process_start", process_start_ns))

    def mark(self, name):
        if self.closed:
            raise RuntimeError("启动时间线已经结束")
        self.events.append((name, self.clock_ns()))

    def finish(self):
        self.closed = True
        events = dict(self.events)
        timings = []
        for index, (name, stamp) in enumerate(self.events):
            previous = self.events[index - 1][1] if index else None
            timings.append({
                "event": name,
                "since_process_start_s": round((stamp - events["process_start"]) / 1e9, 4)
                if "process_start" in events else None,
                "since_previous_s": round((stamp - previous) / 1e9, 4)
                if previous is not None else None,
            })
        return {
            "timeline": timings,
            "time_to_first_frame_s": round(
                (events["first_rendered_frame"] - events["process_start"]) / 1e9, 4
            ) if {"process_start", "first_rendered_frame"} <= events.keys() else None,
            "time_to_menu_usable_s": round(
                (events["main_menu_usable"] - events["process_start"]) / 1e9, 4
            ) if {"process_start", "main_menu_usable"} <= events.keys() else None,
            "clock": (
                "time.perf_counter_ns; process origin supplied before Popen"
                if "process_start" in events else "time.perf_counter_ns; relative transition"
            ),
        }
