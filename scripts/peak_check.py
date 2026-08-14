#!/usr/bin/env python3
"""DeepSeek 高峰时段判断（北京时间）。0 token。
高峰: 09:00-12:00, 14:00-18:00；其余为空闲。
输出: PEAK/OFFPEAK + 北京时间。退出码: 0=高峰, 1=空闲。
用法: python3 peak_check.py
"""
import datetime as dt

def is_peak(hour: int, minute: int) -> bool:
    t = hour * 60 + minute
    return (9 * 60 <= t < 12 * 60) or (14 * 60 <= t < 18 * 60)

now = dt.datetime.now(dt.timezone(dt.timedelta(hours=8)))
peak = is_peak(now.hour, now.minute)
print("PEAK" if peak else "OFFPEAK")
print(now.strftime("%Y-%m-%d %H:%M:%S CST"))
raise SystemExit(0 if peak else 1)
