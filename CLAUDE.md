# CLAUDE.md

实验室 Raman/PL 光谱自动化平台。控制真实激光硬件——**安全永远优先于功能**。

## 项目背景（30秒版）

把老师的人工测量 SOP（`docs/lab-sop-pl-mapping-zolix-ocr.md`）自动化：WayneLabs 电动位移台（串口）+ Zolix 光谱仪（DLL）+ DField CCD（DLL）+ PWM 激光/LED 光源（Modbus RTU）。分层：`devices/raw/`（协议）→ `devices/`（适配器）→ `workflow/`（单点测量/托盘扫描）→ `cli.py`（ramanctl）+ `api/`（FastAPI）→ `frontend/`（React）。开发在 macOS 上以 dry-run/simulated 模式进行；真机是实验室 Windows 64 位机器。完整说明见 `README.md`，真机部署见 `docs/lab-setup.md`。

## 当前状态

@docs/PROJECT_STATUS.md

## 常用命令

- 测试：`.venv/bin/python -m pytest -q`（venv 用 `uv venv .venv --python 3.12` + `uv pip install -e ".[dev,api]"` 创建）
- 后端：`./scripts/start_api.sh`（http://127.0.0.1:8008）；前端：`./scripts/start_frontend.sh`
- 前端验证：`cd frontend && npm test && npm run lint && npm run build`

## 安全红线（改代码前必读）

- 激光相关的异常路径必须收敛到"确认关闭"：工作流失败/取消一律走 `_confirm_laser_off_after_failure`；PWM 关断必须读回确认。
- 不要绕过单线程硬件队列直接开串口；设备端点忙时返回 409。
- 不要恢复 `/light/on` 端点或任何无确认的激光开启通道。
- 参数硬上限（exposure≤60s、frames≤1000、burn_threshold>0）不许放宽，除非用户明确要求。
- 工作风格约定见 AGENTS.md（最小改动、外科手术式、先 dry-run 后真机）。

## 状态文档维护约定（Agent 必须遵守）

`docs/PROJECT_STATUS.md` 是跨 session 的项目记忆。**每次 git commit 之后、以及完成一段实质性工作准备结束回合前，检查并更新它**：当前阶段、最近完成、下一步、已知问题，并把「最后更新」改为当天日期。有 hooks 强制这条约定（提交后注入提醒；状态文档比最新提交旧时会阻止结束回合）。更新原则：写"现在在哪、接下来去哪"，不堆流水账；被完成的"下一步"要移走，新发现的问题要补进"已知问题"。
