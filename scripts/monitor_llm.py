#!/usr/bin/env python3
"""monitor 模式辅助: 输出队列中 llm 任务文本。
无 llm 任务 → 空输出 → cron monitor 判定输出未变化 → agent 不运行 (0 token)。
有新增/变更 llm 任务 → 输出变化 → 触发 agent 处理。
用法: python3 monitor_llm.py
"""
import json
import os

QUEUE = os.path.join(os.path.expanduser("~"), ".hermes", "queued-tasks.jsonl")
if "HERMES_HOME" in os.environ and os.path.isdir(os.environ["HERMES_HOME"]):
    QUEUE = os.path.join(os.environ["HERMES_HOME"], "queued-tasks.jsonl")

if not os.path.exists(QUEUE):
    raise SystemExit(0)

out = []
for line in open(QUEUE, encoding="utf-8"):
    line = line.strip()
    if not line:
        continue
    try:
        t = json.loads(line)
    except json.JSONDecodeError:
        continue
    if t.get("type") == "llm":
        body = (t.get("prompt") or "").replace("\n", " ")[:200]
        out.append(f"#{t['id']} {t.get('desc','')} :: {body}")
print("\n".join(out))
