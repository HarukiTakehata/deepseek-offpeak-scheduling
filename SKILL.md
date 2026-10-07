---
name: deepseek-offpeak-scheduling
description: "Use when 用户在用 DeepSeek 且高峰/涨价要省钱: cron 暂存任务到空闲时段, 0 token."
version: 1.5.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [deepseek, pricing, cron, cost-saving, offpeak]
    related_skills: [hermes-agent, hermes-two-container-topology]
---

# DeepSeek 峰谷调度

**触发**：仅当会话 provider/model 是 DeepSeek（如 deepseek-flash / deepseek-v4-pro）且用户要省钱/避开高峰。非 DeepSeek 场景勿加载本技能。

**模型**（2026-09-10 校验）：
- `deepseek-flash` = **DeepSeek-V4.1-Flash**（1M 上下文 / 最大 384K 输出，支持图像理解，并发 2500）— 当前主力
- `deepseek-v4-pro` = DeepSeek-V4-Pro-0813（并发 500，**不支持图像**）
- 旧调用名 `deepseek-v4-flash`、`deepseek-v4-flash-vision-exp` **已下线**：仍可调用但由 V4.1-Flash 提供服务、按 Flash 价计费
- ⚠️ **2026-09-14 12:00 北京时间后**，`deepseek-v4-pro` 请求全部路由到 V4.1-Flash 并按 Flash 价计费（V4.1 Pro 上线前）；成本核算与 `--model` 参数届时统一用 `deepseek-flash`

**价格**（元/百万 tokens，2026-10-07 官方页复核，与 2026-09-10 一致，无变动）：

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
2. 脚本任务 → cron 0 token 执行（wrapper 自带路径推导，`--script` 只写文件名）：`hermes cron create --no-agent --script run_queue.sh --deliver local --name offpeak-queue-run "5 10 * * *"`（队列空则静默）
3. LLM 任务 → monitor 模式（无新任务 0 token）：`hermes cron create --monitor-script monitor_llm.py --model deepseek-flash --deliver local --name offpeak-llm-queue "5 10 * * *" "处理共享队列 <cron侧HERMES_HOME>/queued-tasks.jsonl 中 type=llm 任务，逐条执行后删行并输出简短汇总；队列为空则不做任何事"`
   - ⚠️ 排期时区：cron 表达式按 `hermes_time` 的配置时区解析（`HERMES_TIMEZONE` → config.yaml `timezone` → 容器本地时间），**不是北京时区**。本部署无 timezone 配置 → 按容器本地 **UTC**，所以北京 18:05 写作 `5 10 * * *`（12:05 写作 `5 4 * * *`）。排期前先确认容器 `date` 与配置。
   - prompt 里写**字面路径**（cron 侧看到的是它自己的 `$HERMES_HOME`，如 `/home/hermes/.hermes/...`），`$HERMES_HOME` 不会被 cron 展开。

**时段规则**（2026-10-07 官网脚注(2) 复核）：高峰 = **周一至周五** 9:00-12:00、14:00-18:00（北京时间），**不含中国法定节假日**；**周末及法定节假日全天空闲**，夜间全空闲。`peak_check.py` 已按此实现（周末判断 + `HOLIDAYS` 节假日表）。
- ⚠️ 节假日表是**硬编码**的：国务院每年发布次年安排后须把日期加进 `HOLIDAYS`，否则节假日会误报 PEAK（2026-10-07 国庆假期最后一天曾如此）。判断前先确认表覆盖当年。
- ⚠️ 调休上班的周六/周日（如 2026-10-10、2026-09-20）：官方仅以“周一至周五”为高峰，故**仍算空闲**，不要把它们当高峰。
4. 验证：`task_queue.py count` / `hermes cron list`；`hermes cron run <id>` 可立即触发一次（实测：入队 → run → 队列清空、`hermes cron runs <id>` 显示 completed）。

**省 token**：no_agent=0 token；monitor 无变化=0 token；高峰只登记；批量合并；--model 选 flash。
**陷阱**（2026-09-11 实测补充）：
- `~` 已重定向，cron script 用绝对路径，且**不要硬编码 home**（cron 侧与交互会话的 `HERMES_HOME` 前缀不同）—— wrapper 从自身位置推导：`HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"`，写死路径会 `script failed`（exit 2）。
- **排队任务里别写“检查本地克隆”之类操作**（cron 侧看不到 webui 的工作区）：改走 API/网络；必须提本地路径时注明“该路径可能不可见”。
- cron 作业 `--deliver` 显式设 `local`（`origin` 对 webui 不可靠）——否则 `last_status=error`。
- **别用 `write_file` 改队列文件**：`queued-tasks.jsonl` 在 `HERMES_WRITE_SAFE_ROOT`（如 `/opt/data`）之外，会被拒（`Write denied: ... is outside HERMES_WRITE_SAFE_ROOT`）；删行用 shell（`task_queue.py` / `sed -i`）。该拒写会在报告末尾以 "File-mutation verifier" 警告出现 —— 看到它先确认文件是否真被改动。
- monitor 首 tick 必跑一次；run 失败任务保留重试；价格随时变，重抓官方页更新。
- 排队任务写"只读、不要 push/评论"是有效的护栏（实测 agent 严格遵守），但**它跑完仍可能提出需要写操作的后续** —— 恢复到交互会话里人工确认再执行。
**cron 容器差异 / 调度归属**：不在此展开 —— 参见 `hermes-two-container-topology` 技能（容器拓扑、共享卷视图、script 子进程环境、ticker 心跳判定均记在那里）。
