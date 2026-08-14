#!/usr/bin/env python3
"""DeepSeek 峰谷调度任务队列 (JSONL)。

用法:
  python3 task_queue.py enqueue --cmd "bash xxx.sh" [--desc 描述]   # 脚本任务(no_agent 0 token 执行)
  python3 task_queue.py enqueue --prompt "提示词" [--desc 描述]      # LLM 任务(agent 模式执行)
  python3 task_queue.py list [--type cmd|llm]
  python3 task_queue.py count
  python3 task_queue.py run            # 执行全部 cmd 任务: 成功出队, 失败保留; 输出执行报告

队列文件: $HERMES_HOME/queued-tasks.jsonl (默认 ~/.hermes/queued-tasks.jsonl)
"""
import argparse
import datetime as dt
import json
import os
import subprocess
import sys

QUEUE = os.path.join(os.path.expanduser("~"), ".hermes", "queued-tasks.jsonl")
# 若 HOME 被重定向且真实 HERMES_HOME 存在，优先用 HERMES_HOME
if "HERMES_HOME" in os.environ:
    cand = os.path.join(os.environ["HERMES_HOME"], "queued-tasks.jsonl")
    if os.path.isdir(os.environ["HERMES_HOME"]):
        QUEUE = cand


def now():
    return dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).isoformat(timespec="seconds")


def load():
    if not os.path.exists(QUEUE):
        return []
    with open(QUEUE, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def save(items):
    os.makedirs(os.path.dirname(QUEUE), exist_ok=True)
    with open(QUEUE, "w", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")


def enqueue(args):
    if not args.cmd and not args.prompt:
        sys.exit("error: 需要 --cmd 或 --prompt")
    items = load()
    task = {
        "id": (items[-1]["id"] + 1) if items else 1,
        "type": "cmd" if args.cmd else "llm",
        "cmd": args.cmd,
        "prompt": args.prompt,
        "desc": args.desc or "",
        "enqueued_at": now(),
    }
    items.append(task)
    save(items)
    body = (task["cmd"] or task["prompt"] or "")[:50]
    print(f"enqueued #{task['id']} [{task['type']}] {task['desc'] or body} @ {task['enqueued_at']}")
    print(f"queue: {QUEUE}")


def list_tasks(args):
    items = load()
    if not items:
        print("(queue empty)")
        return
    for it in items:
        if args.type and it["type"] != args.type:
            continue
        body = (it.get("cmd") or it.get("prompt") or "").replace("\n", " ")[:80]
        print(f"#{it['id']} [{it['type']}] {it.get('desc','')} :: {body}  (enqueued {it.get('enqueued_at','')})")


def count(args):
    items = load()
    print(f"total={len(items)} cmd={sum(1 for i in items if i['type']=='cmd')} llm={sum(1 for i in items if i['type']=='llm')}")


def run(args):
    """执行全部 cmd 任务。成功出队，失败保留(下次重试)。队列空→输出空(no_agent 静默)。"""
    items = load()
    cmd_items = [i for i in items if i["type"] == "cmd"]
    if not cmd_items:
        return 0  # 空输出 = no_agent 模式静默
    done, failed = [], []
    report = [f"== 队列执行报告 {now()} =="]
    for it in cmd_items:
        body = it.get("cmd") or ""
        try:
            r = subprocess.run(["bash", "-c", body], capture_output=True, text=True, timeout=600)
            if r.returncode == 0:
                done.append(it)
                tail = (r.stdout or "").strip().splitlines()[-3:]
                report.append(f"#OK {it['id']} {it.get('desc') or body[:60]}")
                for ln in tail:
                    report.append("    " + ln[:120])
            else:
                it["retries"] = it.get("retries", 0) + 1
                failed.append(it)
                report.append(f"#FAIL(retry={it['retries']}) {it['id']} {it.get('desc') or body[:60]}")
                err = (r.stderr or "").strip().splitlines()[-2:]
                for ln in err:
                    report.append("    ERR " + ln[:120])
        except Exception as e:  # timeout 等
            it["retries"] = it.get("retries", 0) + 1
            failed.append(it)
            report.append(f"#EXC {it['id']} {e}")
    save([i for i in items if i not in done])  # 失败保留，下次 cron 重试
    print("\n".join(report))
    print(f"== 完成 {len(done)} 失败 {len(failed)} 队列剩余 {len(load())} ==")
    return 0


def main():
    p = argparse.ArgumentParser(prog="task_queue.py", description="DeepSeek 峰谷调度任务队列")
    sub = p.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("enqueue", help="暂存任务")
    e.add_argument("--cmd", help="脚本命令 (cmd 类型)")
    e.add_argument("--prompt", help="LLM 提示词 (llm 类型)")
    e.add_argument("--desc", default="", help="描述")
    e.set_defaults(fn=enqueue)
    l = sub.add_parser("list", help="列出任务")
    l.add_argument("--type", choices=["cmd", "llm"], help="按类型过滤")
    l.set_defaults(fn=list_tasks)
    c = sub.add_parser("count", help="统计")
    c.set_defaults(fn=count)
    r = sub.add_parser("run", help="执行 cmd 任务")
    r.set_defaults(fn=run)
    args = p.parse_args()
    sys.exit(args.fn(args) or 0)


if __name__ == "__main__":
    main()
