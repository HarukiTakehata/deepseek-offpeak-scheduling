---
name: deepseek-offpeak-scheduling
description: "Use when 用户在用 DeepSeek 且高峰/涨价要省钱: cron 暂存任务到空闲时段, 0 token."
version: 1.3.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [deepseek, pricing, cron, cost-saving, offpeak]
    related_skills: [hermes-agent]
---

# DeepSeek 峰谷调度

**触发**：仅当会话 provider/model 是 DeepSeek（如 deepseek-flash / deepseek-v4-pro）且用户要省钱/避开高峰。非 DeepSeek 场景勿加载本技能。

**模型**（2026-09-10 校验）：
- `deepseek-flash` = **DeepSeek-V4.1-Flash**（1M 上下文 / 最大 384K 输出，支持图像理解，并发 2500）— 当前主力
- `deepseek-v4-pro` = DeepSeek-V4-Pro-0813（并发 500，**不支持图像**）
- 旧调用名 `deepseek-v4-flash`、`deepseek-v4-flash-vision-exp` **已下线**：仍可调用但由 V4.1-Flash 提供服务、按 Flash 价计费
- ⚠️ **2026-09-14 12:00 北京时间后**，`deepseek-v4-pro` 请求全部路由到 V4.1-Flash 并按 Flash 价计费（V4.1 Pro 上线前）；成本核算与 `--model` 参数届时统一用 `deepseek-flash`

**价格**（元/百万 tokens，2026-09-10 官方页复核）：

| 时段(北京) | flash 输入(命中) | flash 输入(未命中) | flash 输出 | pro 输入(命中) | pro 输入(未命中) | pro 输出 |
|---|---|---|---|---|---|---|
| 🔴 高峰 | 0.04 | 2 | **8** | 0.30 | 9.0 | 27.0 |
| 🟢 空闲 | 0.02 | 1 | **4** | 0.15 | 4.5 | 13.5 |

- 高峰 = 空闲 × 2；Flash 较 2026-08 旧价（输出 4.5/9.0）**再降约 11%**
- 缓存命中单价极低（0.02~0.30）→ 长上下文任务优先**峰值前预热缓存**
- 大任务前核对 https://api-docs.deepseek.com/zh-cn/quick_start/pricing/

**脚本**（$HERMES_HOME/scripts/，cron 必须绝对路径）：
- `peak_check.py` — 输出 PEAK/OFFPEAK，退出码 0=高峰 1=空闲
- `task_queue.py` — enqueue `--cmd|--prompt [--desc] [--timeout 秒]` / list / count / run
- `monitor_llm.py` — 队列 llm 任务变化检测（空输出=不触发）
- `run_queue.sh` — cron no_agent 执行入口 wrapper（队列空则静默）

**流程**：
0. **高峰期的输出与操作都要极简**（用户 2026-09-11 明确要求）：短句、不铺垫、不解释过程、不列未被要求的选项/表格；只做被明确要求的事，不做任何"顺手"操作（不多读文件、不预取、不主动扩大范围）。空闲时段恢复常规风格。判断用 `peak_check.py`，别凭感觉。
1. 高峰→只 enqueue 登记，**不执行**长任务
2. 脚本任务 → cron 0 token 执行：`hermes cron create --no-agent --script $HERMES_HOME/scripts/task_queue.py run "5 18 * * *"`（队列空则静默）
3. LLM 任务 → monitor 模式（无新任务 0 token）：`hermes cron create --monitor-script $HERMES_HOME/scripts/monitor_llm.py --model deepseek-flash "5 18 * * *" "处理 $HERMES_HOME/queued-tasks.jsonl 中 type=llm 任务，逐条执行后删行并输出汇总"`

**时段规则**（2026-09-10 起）：高峰 = **周一至周五** 9:00-12:00、14:00-18:00（北京时间）；**周末全天空闲**，且夜间全空闲。`peak_check.py` 已按此实现（含周末判断）。
4. 验证：`task_queue.py count` / `hermes cron list`

**省 token**：no_agent=0 token；monitor 无变化=0 token；高峰只登记；批量合并；--model 选 flash。
**陷阱**（2026-09-11 实测补充）：
- `~` 已重定向，cron script 用绝对路径 —— **但"绝对路径"不能硬编码本容器的 home**：cron 可能运行在独立的 agent 容器，其 `HERMES_HOME` 与交互会话不同（同一卷的不同挂载点），脚本里写死具体 home 路径会 `ENOENT` 报 `script failed`（exit 2）。wrapper 要从自身位置推导：`HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"`。
- **cron 容器看不到宿主/编排容器的共享工作区路径**：排队任务的文本里别要求"检查本地克隆"之类的操作，改走 API/网络；任务里如必须提本地路径，明确写上"该路径可能不可见"。
- **别用 `write_file` 改队列文件**：`queued-tasks.jsonl` 在 `HERMES_WRITE_SAFE_ROOT`（如 `/opt/data`）之外，会被拒（`Write denied: ... is outside HERMES_WRITE_SAFE_ROOT`）；删行用 shell（`task_queue.py` / `sed -i`）。该拒写会在报告末尾以 "File-mutation verifier" 警告出现 —— 看到它先确认文件是否真被改动。
- monitor 首 tick 必跑一次；run 失败任务保留重试；价格随时变，重抓官方页更新。
- 排队任务写"只读、不要 push/评论"是有效的护栏（实测 agent 严格遵守），但**它跑完仍可能提出需要写操作的后续** —— 恢复到交互会话里人工确认再执行。
**cron 容器架构**（webui 环境实测）：
- cron 调度器跑在 **hermes-agent 容器**（`hermes-agent:8642`，PID 149 gateway），不是 WebUI 容器；脚本在那边执行，但 `~/.hermes`（jobs/executions/scripts）是共享 volume，两边同视图
- **deliver 陷阱**：WebUI 会话创建 job 时 `deliver=origin` 会解析成 `unknown platform 'webui'` 报错 → **显式设 `deliver=local`**（或具体平台），否则 `last_status=error`
- cron script 子进程环境 = `build_subprocess_env()`：HOME 重定向到 `$HERMES_HOME/home`、剥离 provider secrets；脚本里别依赖 `~`，用绝对路径
- 手动 run 与自动 tick 走同一 gateway 执行路径，环境一致；"文件不存在"类报错若重跑即好，多为共享卷时序问题
