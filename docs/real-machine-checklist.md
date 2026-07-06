# 真机确认清单（实验室 Windows 机器）

> **给实验室机器上的 Agent**：这是你在真机上的主任务清单。先读 CLAUDE.md 和 docs/PROJECT_STATUS.md 建立上下文。
> 按顺序执行；每完成一项，把实测值和结论写入当天的验收报告 `docs/hardware-acceptance-report-YYYYMMDD.md`（格式参考 `docs/hardware-acceptance-report-20260624.md`），偏离预期的现象同步写入 PROJECT_STATUS.md 的「已知问题」。
>
> **安全前提（每次 real 操作前逐条确认）**：操作员在场；物理急停/激光钥匙开关可及；样品台上没有贵重样品（除非该项明确需要）；先 dry-run 演练再 real。凡涉及激光开启的步骤，先向操作员口头确认再执行。

## 0. 环境搭建与基线

- [ ] 按 `docs/windows/WINDOWS_SETUP.md` 部署；Python 必须是 **3.11+ 64 位**（DLL 是 64 位的）。
- [ ] `pip install -e ".[dev,api]"`（或 uv）；前端需要时 `cd frontend && npm ci`。
- [ ] **基线测试**：`python -m pytest -q` → 期望 **462 passed, 2 skipped**。数字不符先停下调查，不要带病上硬件。
- [ ] `scripts\check_ports.bat` 记录本机全部 COM 口清单（已知：位移台 COM4；待确认：物镜转盘 COM5、光路切换 COM16、半波片 COM17、PWM 光源端口）。
- [ ] 从 `configs/devices.example.yaml` 建立 `configs/devices.yaml`，按实测填端口。
- [ ] hooks 依赖 Git Bash（Git for Windows 自带）；若 Stop/PostToolUse hook 报错，确认 `bash` 在 PATH。

## 1. P0 安全修复真机验证（最优先；1.x 全过之前不做第 2、3 节）

P0 改动（commit `3429b52`，明细见 CHANGELOG「P0 安全修复」）只在模拟层验证过，以下逐项在真机确认：

- [ ] **1.1 上电安全复位**：用厂家调试工具（或直接 Modbus 写寄存器）把一个非激光通道置 ON → 运行 `ramanctl` 任一需要光源的命令或启动 API → 判据：创建光源时全部通道被关断且读回为 0；API 启动日志出现 "power-on laser safety reset confirmed"。
- [ ] **1.2 紧急停止端点**：dry-run 提交一个任务，任务运行中 `POST /api/emergency-stop` → 判据：响应 `laser_off: "confirmed"`，任务被取消。再在 real 模式短曝光任务中重复 → 判据：激光实际熄灭（目视/功率计）。
- [ ] **1.3 协作式取消**：real 模式单点测量（短曝光、废样品），进度中点 Web「停止」→ 判据：状态走 stopping→stopped；激光实际熄灭；不出现「前端说停了、激光还亮」。
- [ ] **1.4 串口参数与 Modbus 健壮性**：确认 PWM 控制器实际是 8N1 还是 8E1（协议文档 vs 实测）；正常读写往返稳定；有条件时拔插/干扰一次串口，确认失步后自愈（重试日志）而不是永久 manual_wait。
- [ ] **1.5 位置台账崩溃安全**：X 轴发起一次小行程移动（如 500 µm），移动中杀掉进程（任务管理器）→ 重启 → 判据：该轴状态为 UNKNOWN、拒绝大距离移动、要求重新 home。⚠️ 电机会走完剩余行程，确认行程范围内无碰撞风险再做。
- [ ] **1.6 home 方向实测**：低速、手悬急停，分别观察各轴 home 的安全方向 → 把实测方向写入 `devices.yaml` 的 `stage.home_direction` → 再故意用反方向调 home，判据：被 SafetyError 拒绝。
- [ ] **1.7 参数上限**：配置 `exposure_ms: 60001` → 判据：被拒绝且报错信息包含 "safety cap"。

## 2. 审计标记的「只有真机能确认」项

- [ ] **2.1 激光斑 = 图像中心**（M2 全部标定的前提假设）：成像模式下打开激光最低功率，拍照测激光斑心与图像几何中心的像素偏差。偏差显著则记录数值——M2 标定要加偏移项。
- [ ] **2.2 软限位与分辨率实测**：当前 `resolution_um: 0.04`、软限位 ±5000/±1000 是旧代码注释的占位值。实测各轴行程与每步位移，替换 `devices.yaml` 占位值并记录依据。
- [ ] **2.3 ctypes 边界用例**（防原生堆破坏）：用 ROI 宽/高**不能被 bin 整除**的组合采集（如 ROI 宽 7、bin_x 2），判据：返回尺寸与预期一致、进程不崩溃。多试几组边界。
- [ ] **2.4 FVB 残留 ROI**：先做一次 image 模式 + ROI 采集，紧接 FVB 采集 → 判据：FVB 结果不受残留 ROI 影响（长度 2048）。
- [ ] **2.5 Phase 2 M1 遗留读回**（见 `docs/phase2-hardware-acceptance.md`）：Reg1 显式读回 == 0x0032；关闭后全通道读回为 0。
- [ ] **2.6 identify 分包观察**：多次运行 stage identify，若出现「首响应不完整→报错」即命中审计已知问题（分包解析），记录频率，回报后修。

## 3. 信息采集（为 P1/P2 填坑）

- [ ] **3.1 三个未建模串口子系统探查**：⚠️ **不要向身份未确认的 COM 口发送任何指令**——先向老师/师兄要旧控制代码（`changelight.py`、`lenschange.py`、`lasermove.py`）确认协议，再逐口验证。目标：记录 COM5（物镜转盘）、COM16（光路切换 Image-LED ↔ PL/Raman）、COM17（半波片功率）的波特率、指令集、响应格式，存入 `docs/` 供后续建模。
- [ ] **3.2 `configs/tray_scan.real.yaml` 的 `<FILL>` 采集**：像素↔位移台仿射标定（按当前物镜）、样品盘几何、burn_threshold（用一对已知良谱标定）、min_area、calibration 的 image_width_px/height_px（**必填**，防识别缩放导致激光脱靶）。
- [ ] **3.3 CCD 冷却与温度**：读 `temperature_c()` 记录环境值；确认 `a4_set_cooling_temp` 是否可用及到温时间（P2 控温功能的输入）。

## 4. 记录纪律

- 每完成一节就 commit（hooks 会提醒维护 PROJECT_STATUS.md）。
- 所有实测数值（端口、分辨率、限位、偏差、阈值）必须落在验收报告里，不能只留在配置文件——配置是 gitignored 的。
- 遇到与 dry-run/simulated 行为不一致的任何现象，无论多小，记入验收报告「Deviations」段——这些是修正模拟层的输入。
