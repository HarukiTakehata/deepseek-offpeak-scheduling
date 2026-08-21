---
name: deepseek-offpeak-scheduling
description: "Use when 用户在用 DeepSeek 且高峰/涨价要省钱: cron 暂存任务到空闲时段, 0 token."
version: 1.2.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [deepseek, pricing, cron, cost-saving, offpeak]
    related_skills: [hermes-agent]
---

# DeepSeek 峰谷调度

**触发**：仅当会话 provider/model 是 DeepSeek（如 deepseek-v4-flash/pro）且用户要省钱/避开高峰。非 DeepSeek 场景勿加载本技能。

**模型**（2026-08 校验）：`deepseek-v4-flash`=V4-Flash-0731，`deepseek-v4-pro`=V4-Pro-0813（版本升级调用名不变）；新增实验模型 `deepseek-v4-flash-vision-exp`（支持图像输入，价格同 flash，生产慎用）。

**价格**（2026-08-17 00:00 北京时间起，元/百万 tokens，2026-08-21 复核未变）：

| 时段(北京) | flash 输出 | pro 输出 |
|---|---|---|
| 🔴 高峰 9-12点、14-18点 | 9.0 | 27.0 |
| 🟢 空闲 其余时间 | 4.5 | 13.5 |

输入（缓存未命中）：flash 1.5/高峰 3.0，pro 4.5/高峰 9.0；缓存命中仅 0.05~0.30 可忽略 → 长上下文任务优先**峰值前预热缓存**。

高峰=空闲×2；对比旧价（flash 输出 2元/M）高峰贵 4.5 倍。大任务前核对 https://api-docs.deepseek.com/zh-cn/quick_start/pricing/

**脚本**（$HERMES_HOME/scripts/，cron 必须绝对路径）：
- `peak_check.py` — 输出 PEAK/OFFPEAK，退出码 0=高峰 1=空闲
- `task_queue.py` — enqueue `--cmd|--prompt [--desc] [--timeout 秒]` / list / count / run
- `monitor_llm.py` — 队列 llm 任务变化检测（空输出=不触发）
- `run_queue.sh` — cron no_agent 执行入口 wrapper（队列空则静默）

**流程**：
1. 高峰→只 enqueue 登记，**不执行**长任务
2. 脚本任务 → cron 0 token 执行：`hermes cron create --no-agent --script $HERMES_HOME/scripts/task_queue.py run "5 18 * * *"`（队列空则静默）
3. LLM 任务 → monitor 模式（无新任务 0 token）：`hermes cron create --monitor-script $HERMES_HOME/scripts/monitor_llm.py --model deepseek-v4-flash "5 18 * * *" "处理 $HERMES_HOME/queued-tasks.jsonl 中 type=llm 任务，逐条执行后删行并输出汇总"`
4. 验证：`task_queue.py count` / `hermes cron list`

**省 token**：no_agent=0 token；monitor 无变化=0 token；高峰只登记；批量合并；--model 选 flash。
**陷阱**：`~` 已重定向，cron script 用绝对路径；monitor 首 tick 必跑一次；run 失败任务保留重试；价格随时变，重抓官方页更新。
**cron 容器架构**（webui 环境实测）：
- cron 调度器跑在 **hermes-agent 容器**（`hermes-agent:8642`，PID 149 gateway），不是 WebUI 容器；脚本在那边执行，但 `~/.hermes`（jobs/executions/scripts）是共享 volume，两边同视图
- **deliver 陷阱**：WebUI 会话创建 job 时 `deliver=origin` 会解析成 `unknown platform 'webui'` 报错 → **显式设 `deliver=local`**（或具体平台），否则 `last_status=error`
- cron script 子进程环境 = `build_subprocess_env()`：HOME 重定向到 `$HERMES_HOME/home`、剥离 provider secrets；脚本里别依赖 `~`，用绝对路径
- 手动 run 与自动 tick 走同一 gateway 执行路径，环境一致；"文件不存在"类报错若重跑即好，多为共享卷时序问题
