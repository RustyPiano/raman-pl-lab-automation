# 项目状态（活文档）

> 本文档由 Agent 在每次实质性进展后主动维护（hooks 强制，见 CLAUDE.md「状态文档维护约定」）。
> 只记录"现在在哪、接下来去哪"；历史细节归 CHANGELOG.md。

**最后更新**：2026-07-07

## 当前阶段

P0 激光安全修复已完成并提交（`3429b52`），**尚未在实验室 Windows 真机上验证**。下一阶段是 P1（真机验收窗口）。

## 最近完成

- 建立跨 session 项目记忆系统：CLAUDE.md（背景+安全红线+约定）+ 本状态文档 + hooks 强制维护（提交后提醒、状态过期阻止结束回合）。
- P0 安全修复全量落地：激光安全闭环（上电复位/atexit/紧急停止端点）、协作式取消（stopping 状态+检查点）、堵死 input() 挂死链、设备端点重写（删除 /light/on）、Modbus 失步自愈、位置台账两阶段写、参数硬上限。详见 CHANGELOG「P0 安全修复」。
- 测试基线：`pytest -q` 462 passed, 2 skipped；`npm run build` 通过。
- 完整盲点审计报告（80+ 发现、P0-P3 路线图）：https://claude.ai/code/artifact/880e32ba-4352-454f-98ee-1a9c1fe538bb

## 下一步（按优先级）

0. **真机确认**：仓库即将部署到实验室 Windows 机器。真机上的工作入口是 `docs/real-machine-checklist.md`（环境基线 → P0 真机验证 → 审计真机项 → 信息采集），实测结果写验收报告。
1. **P1 - 需要老师决策**：三个真机才发现、至今未建模的串口子系统的范围决策——COM16 光路切换（阻塞 M2）、COM17 半波片（决定激光功率能否进软件闭环）、COM5 物镜转盘。
2. **P1 - 代码**：接通托盘扫描识别链路（FileMaskProvider + 掩码 session/时间戳握手）；打通前端光谱结果链路（后端 result 带数据 → 前端 completed 后回查）。
3. **P1 - 真机验收清单**：激光斑=图像中心实测、软限位/resolution_um 实测、串口 8N1 vs 8E1、home 方向实测后写入 `home_direction` 配置、ROI 非整除 bin 的 ctypes 边界用例。
4. **P2**：科学元数据补全（激发波长/软件版本/配置快照/探测器温度）、标定验证工序、烧检修正、宇宙射线剔除、CCD 控温。
5. **P3**：认证+审计日志、任务持久化、Phase B UI（托盘扫描/设备监控/历史）。

## 已知问题 / 待决事项

- `/light/off` 在任务运行中与串口有竞态（Windows 下第二次 open 失败返回 400，方向安全）；紧急场景用 `/api/emergency-stop`。
- waynelabs identify 首响应分包解析未修（审计中级项）；serial `exclusive=True` 未加。
- 真机验收前不要跑 real 模式的托盘扫描：识别链路未接线，`scan tray --real` 必然失败。
- `configs/tray_scan.real.yaml` 的标定/几何/burn 阈值全是 `<FILL>`，需真机采集。
