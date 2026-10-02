#!/usr/bin/env python3
"""DeepSeek 高峰时段判断（北京时间）。0 token。

高峰: 周一至周五 09:00-12:00, 14:00-18:00；其余（含周末全天、夜间）为空闲。
依据官方定价页 2026-09-10 复核。
输出: PEAK/OFFPEAK + 北京时间。退出码: 0=高峰, 1=空闲。
用法: python3 peak_check.py
"""
import datetime as dt

PEAK_WINDOWS = ((9 * 60, 12 * 60), (14 * 60, 18 * 60))


def is_peak(weekday: int, hour: int, minute: int) -> bool:
    """weekday: 0=周一 ... 6=周日。周末全天空闲。"""
    if weekday >= 5:
        return False
    t = hour * 60 + minute
    return any(start <= t < end for start, end in PEAK_WINDOWS)


now = dt.datetime.now(dt.timezone(dt.timedelta(hours=8)))
peak = is_peak(now.weekday(), now.hour, now.minute)
print("PEAK" if peak else "OFFPEAK")
print(now.strftime("%Y-%m-%d %H:%M:%S CST") + " " + "周" + "一二三四五六日"[now.weekday()])
raise SystemExit(0 if peak else 1)
