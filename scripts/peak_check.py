#!/usr/bin/env python3
"""DeepSeek 高峰时段判断（北京时间）。0 token。

高峰: 周一至周五 09:00-12:00, 14:00-18:00（北京时间）
空闲: 其余时段 + 周末全天 + 中国法定节假日全天
依据官方定价页脚注(2)，2026-10-07 复核。
输出: PEAK/OFFPEAK + 北京时间。退出码: 0=高峰, 1=空闲。
用法: python3 peak_check.py
"""
import datetime as dt

PEAK_WINDOWS = ((9 * 60, 12 * 60), (14 * 60, 18 * 60))

# 中国法定节假日（放假日期，不含调休上班的周末）。
# 官方规则：节假日全天空闲；调休上班的周六/周日仍按“周末=空闲”处理（官方仅以周一至周五为高峰）。
HOLIDAYS = {
    # 2026（国务院办公厅关于2026年部分节假日安排的通知，国办发明电〔2025〕7号）
    "2026-01-01", "2026-01-02", "2026-01-03",             # 元旦
    *(f"2026-02-{d:02d}" for d in range(15, 24)),           # 春节 2/15-2/23
    "2026-04-04", "2026-04-05", "2026-04-06",             # 清明
    *(f"2026-05-{d:02d}" for d in range(1, 6)),            # 劳动节 5/1-5/5
    "2026-06-19", "2026-06-20", "2026-06-21",             # 端午
    "2026-09-25", "2026-09-26", "2026-09-27",             # 中秋
    *(f"2026-10-{d:02d}" for d in range(1, 8)),            # 国庆 10/1-10/7
}


def is_peak(weekday: int, hour: int, minute: int, is_holiday: bool = False) -> bool:
    """weekday: 0=周一 ... 6=周日。周末与法定节假日全天空闲。"""
    if weekday >= 5 or is_holiday:
        return False
    t = hour * 60 + minute
    return any(start <= t < end for start, end in PEAK_WINDOWS)


now = dt.datetime.now(dt.timezone(dt.timedelta(hours=8)))
today = now.strftime("%Y-%m-%d")
holiday = today in HOLIDAYS
peak = is_peak(now.weekday(), now.hour, now.minute, holiday)
print("PEAK" if peak else "OFFPEAK")
print(now.strftime("%Y-%m-%d %H:%M:%S CST") + " " + "周" + "一二三四五六日"[now.weekday()]
      + ("（法定节假日，全天空闲）" if holiday else ""))
raise SystemExit(0 if peak else 1)
