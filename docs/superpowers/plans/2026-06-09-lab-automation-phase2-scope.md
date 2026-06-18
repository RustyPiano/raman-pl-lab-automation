# Lab Automation Phase 2 Scope & Sequencing Plan

> **Status (2026-06-13): Phase 2 M1 code-complete, pending on-hardware acceptance.**
> Phase 1 MVP is code-complete and merged to `main` (`36518da`, `caa3429`).
> Phase 2 M1 PWM Modbus light backend is also implemented and merged to `main`;
> 296 tests pass locally. The only outstanding Phase 1/M1 gates are the
> on-hardware acceptance runs in
> [`docs/phase1-hardware-acceptance.md`](../../phase1-hardware-acceptance.md)
> and [`docs/phase2-hardware-acceptance.md`](../../phase2-hardware-acceptance.md),
> deliberately deferred until the lab Windows machine is available. This
> document now tracks the remaining Phase 2 milestones and the open questions
> that must be answered before any **real-hardware** action ships.

**Source spec:** [`docs/superpowers/specs/2026-06-04-lab-automation-platform-design.md`](../specs/2026-06-04-lab-automation-platform-design.md)
（光源协议 §6.5；安全状态机 §12.2/§12.3；Phase 2 候选范围 §15；风险/待确认 §16；Agent 约束 §17）

**Repository constraints:** [`AGENTS.md`](../../../AGENTS.md)

---

## 1. 指导原则（沿用 Phase 1）

- **严格分层**：`raw -> adapter -> workflow -> CLI -> agent`。Modbus 帧、CRC、寄存器号、HTTP 命令字符串只出现在 `src/lab_auto/devices/raw/*`；上层只看 typed Python API。
- **dry-run / simulated 优先**：每个真实硬件动作都必须先有 dry-run 与 simulated 后端，并被测试覆盖，再上机。
- **安全不可绕过**：激光/归零/长距离移动/Mapping 必须经过安全层；写后读回确认；失败进入人工确认。
- **可审计**：每个实验动作写日志，每次输出保存元数据。
- **无状态 CLI 是默认**；只有显式的 daemon/session 模式（M4）才允许跨命令保留连接，且必须可选、不破坏现有无状态命令。

---

## 2. Phase 2 里程碑与排序

按"安全风险 + 依赖关系 + 可独立验收"排序。每个里程碑都可在不上真机的情况下完成开发与测试，真机验收统一推迟。

| # | 状态 | 里程碑 | 依赖 | 真机前置（上机才确认） |
|---|------|--------|------|------------------------|
| **M1** | 代码完成；待真机验收 | 真实 PWM 光源后端（Modbus RTU） | 无（扩展现有 light 分层） | 通道映射、COM 口、站号、频率/占空比、接线安全、联锁可读性 |
| **M2** | 下一步计划 | 样品盘分层扫描（晶片→掩码→样品中心→每中心3点×2）+ CLI | 依赖 stage 安全状态机（已存在）；复用 M1 光源 + 单点工作流；中心提取/标定/编排自研 | 位移台标定、像素↔位移台标定、样品盘几何、激光斑=图像中心确认 |
| **M3** | 未开始 | 采集后处理增强（峰检测、基线校正、自动曝光、批量调度） | M2（批量调度复用中心点列表扫描） | 无（纯数据处理，可离线验收） |
| **M4** | 未开始 | daemon / session 模式（`ramanctl shell` 或 daemon） | M1–M3 适配器稳定 | 无 |
| **M5** | 未开始 | Agent tool schema + 权限系统 | M1–M4（暴露稳定能力） | 无 |
| **M6** | 阻塞于厂家 API | 厂家 HTTP 光源后端（M1 的替代/补充） | M1；厂家 API 上线 | HTTP 端口、命令字符串、状态读回、错误格式 |

**当前建议先做 M2。** M1 已完成 dry-run/simulated 开发，真实串口验收推迟；M2 能继续推进样品中心定点扫描自动化，并复用现有 stage 安全状态机、M1 光源和单点工作流。识别算法（冯博士）未到不阻塞 M2——M2 只消费"中心点列表"契约，用手填列表即可开发验证。M6 仍是同接口替代后端，等厂家 API 上线再做。

---

## 3. M1：真实 PWM 光源后端（Modbus RTU）—— 详细契约

这是 Phase 2 安全最关键的一块，spec §6.5 / §12.2 / §12.3 已给出完整协议和联锁要求。M1 的 dry-run/simulated 开发已完成，下面保留落地契约供审核和真机验收对照。

### 3.1 文件结构（新增/修改）

```text
src/lab_auto/devices/raw/pwm_modbus.py    # 新增：Modbus RTU 帧编码/解码、CRC16、功能码 0x03/0x06/0x10
src/lab_auto/devices/light.py             # 修改：新增 PwmModbusLight 适配器（与 ManualLight 并存）
src/lab_auto/devices/light_safety.py      # 新增（可选）：光源安全校验，类比 optics_validation.py / dfield_validation.py
src/lab_auto/config.py                    # 修改：扩展 LightConfig（pwm 字段 + channels 映射）
src/lab_auto/devices/factory.py           # 修改：real 模式按 light.type 组装 PwmModbusLight
tests/test_pwm_modbus_protocol.py         # 新增：raw 层帧/CRC/读回校验（平台无关）
tests/test_pwm_light_adapter.py           # 新增：适配器安全联锁（simulated transport）
tests/test_light_config.py                # 新增：LightConfig 解析与拒绝非法配置
```

> raw 层不依赖真实串口：用可注入的 transport（读/写字节）做 simulated，使全部安全逻辑在 macOS 上可测。

### 3.2 寄存器与安全常量（来自 spec §6.5，硬编码进 raw 层）

- `Reg0` 只读；`Reg1-Reg24` 读写；**禁止写 `Reg23`（按键锁）、`Reg24`（波特率）、`Reg25`（未定义）**。
- `Reg1` 全局输出电压，单位 0.1 V。**硬上限 5.0 V**；安全值按十进制 `50` = 寄存器字 `0x0032` = 线缆字节 `00 32`（**不得用 `0x0050`**）。
- `Reg2-Reg11`：CH1–CH5 频率（每通道高/低 16 位组 32-bit Hz）。
- `Reg12-Reg16`：CH1–CH5 占空比，单位 0.1%。
- `Reg17-Reg21`：CH1–CH5 输出状态，`0`=关 `1`=开。
- `Reg22`：当前显示通道（只读用途）。
- 功能码：`0x03` 读、`0x06` 写单、`0x10` 写多。
- **普通读写拒绝 `station_id=0`**；改地址命令（站号 0、单从机）只能在独立维护流程，不进普通工作流。

### 3.3 `laser_on()` / `led_on()` 前置校验序列（强制顺序）

1. 串口已打开；站号非零且有响应。
2. 目标通道映射存在（配置 `channels.laser` / `channels.led`）。
3. `0x03` 读回 `Reg1`，确认 `== 0x0032`。若需写 `Reg1`：先读回 `Reg17-Reg21` 全为 `0`，否则先关闭/人工确认；接线安全确认后才写 `0x0032`，写后再 `0x03` 读回确认。
4. `0x03` 读回 `Reg17-Reg21`，确认非目标/未知通道为 `0`。
5. 读回目标通道频率（`Reg2-Reg11`）和占空比（`Reg12-Reg16`），与配置 `frequency_hz` / `duty_percent` **匹配**，否则拒绝。
6. 写目标通道输出状态，`0x03` 读回对应 `Reg17-Reg21` 确认为 `1`。
7. 仅当上述读回完成：`laser_on()` 才设 `laser_state=on_confirmed`；`led_on()` 只设 `led_state=on_confirmed`，**不得满足 `acquire_sample()` 的激光前置条件**。

**读回有效性**：CRC 正确、响应站号 == 请求非零站号、功能码匹配且非异常响应、byte count 与请求寄存器数一致。仅靠 `0x06`/`0x10` 回帧不算确认，必须 `0x03` 复读。

### 3.4 关闭与异常路径

- `laser_off()` / `led_off()` / 异常处理：best-effort 关闭所有已配置光源通道，`0x03` 读回对应输出状态为 `0`；失败进入人工确认。
- 工作流异常退出：优先关闭所有已配置光源通道并读回 `0`，失败提示人工确认激光关闭（已存在的 `confirm_laser_off` 提示路径复用）。

### 3.5 强度接口

- PWM 后端**默认不暴露** `set_intensity_percent(percent)`。若后续确认需要，只能映射到已验证的单通道 `frequency_hz` / `duty_percent`，**绝不映射到改 `Reg1` 全局电压**。

### 3.6 配置扩展（`LightConfig`）

按 spec §10 注释形态扩展（保持 `ManualLight` 配置向后兼容）：

```yaml
light:
  type: pwm_modbus          # manual | pwm_modbus | pwm_http(M6)
  manual_light_control: false
  port: COMx
  station_id: 1             # 拒绝 0
  baudrate: 9600
  max_output_voltage_v: 5.0     # 硬上限，拒绝更高
  required_output_voltage_v: 5.0
  channels:
    led:   { channel: 1, frequency_hz: 1000, duty_percent: 5.0, default_off_required: true }
    laser: { channel: 2, frequency_hz: 1000, duty_percent: 5.0, default_off_required: true }
```

- 解析必须拒绝：`station_id=0`、`max_output_voltage_v > 5.0`、缺通道映射、未知 `type`。

### 3.7 M1 验收（dry-run / simulated，可在 macOS 完成）

- raw 层：帧编码、CRC、`0x03/0x06/0x10` 往返、坏 CRC/异常响应/站号不符/长度不符全部被拒。
- 适配器：未读回确认时拒绝进入 `on_confirmed`；`led_on()` 不改 `laser_state`；写 `Reg23/24/25` 与 `station_id=0` 被拒；`Reg1` 写入前的 `Reg17-21` 全零检查；写后读回。
- 配置：非法配置被拒并有清晰错误。
- 真机验收（推迟）：新增到 `docs/phase2-hardware-acceptance.md`，覆盖真实 COM 口、通道映射、读回确认、异常关断。

---

## 4. M2–M6 概要契约（详细 TDD 计划在各里程碑开工时再展开）

### M2 样品盘分层扫描（Tray → Wafer → Sample）

> **明确范围（2026-06-18，已与老师确认）**：我们做的**不是**仪器自带的矩形栅格 Mapping（MAPS Sample Stage Mapping，SOP §5）。真实流程是**样品盘分层扫描**：样品盘有多个格子，每格一个晶片，每个晶片上长有几块样品。对每个晶片拍整片照片 → 识别给掩码 → 我们从掩码提取样品中心 → 对每个样品中心做多点单点 Raman。对应 spec **§4.4**，不是 §15 栅格。

**层级与流程：**

```
样品盘 tray ── 多个格子 cells（每格一个晶片 wafer）── 每个晶片上几块样品 samples

1. home：机械限位初始化 → 机器原点
2. for each 晶片（按样品盘已知几何，home + 格子偏移移到晶片中心）：
3.   CCD 拍整个晶片 → 识别算法给【掩码 mask】（外部）
4.   我们从 mask 提取【样品中心】（像素坐标）            ← 中心提取是我们的算法
5.   for each 样品中心：
6.       以【图像中心=原点】，中心像素偏移 → 标定换算成相对移动 → 移到样品中心
7.       测量该样品 = 中心 + 参数化的 2 个周围点，每点单点 Raman ×2（共 6 次）
8.       移回晶片中心（每测完一个样品就回中心，避免误差累积）   ← 已定
9.   该晶片测完 → 移到下一个晶片
```

- 新增 `src/lab_auto/workflow/tray_scan.py` + `ramanctl scan`（命名待定，避免与仪器 mapping 混淆）。复用现有单点工作流（M1 光源 + 减背景时序）做底层"测一个点"。
- **硬前置**：X/Y 轴 `homed`/`user_zeroed`（spec §12.1）；每个目标点在软限位内，越界 skip-或-abort。复用现有 stage 状态机与软限位。
- **每样品中心的采集模式（已定）**：中心 + **参数化图案的 2 个周围点** = 3 个空间点；**每点单点 Raman 重复 2 次**（防误差/防烧样）= 每中心 6 次采集。周围点图案参数化（点数/距离/方向可配，默认 2 点）。
- **坐标系（已定，且因"图像中心=原点"而简化）**：CCD 在晶片中心拍照，所以**图像中心 = 拍照时位移台当前位置**。样品中心相对图像中心的像素偏移 → 像素↔位移台仿射标定 → 即从当前位置出发的相对移动量。测量点假设就在图像中心（= 激光斑，待确认）。标定随物镜倍率变化，按当前倍率取。
- **晶片中心定位（已定）**：样品盘是**已知几何的规则阵列**（行列 + 间距），home 后按格子偏移依次到各晶片中心；不靠逐片识别定位。
- **中心提取是我们的算法（已定）**：冯博士只给识别后的图像/掩码，**从掩码算样品中心由我们实现**（连通域/轮廓 → 质心），数据格式完全我们定。待确认掩码的具体形式（二值 mask / 标签图 / 画框），先按二值/标签 mask 开发。
- **数据模型（我们定）**：
  - `SampleCenter{ pixel_x, pixel_y, label?, area? }`（从掩码提取）
  - `Calibration{ objective, affine 2x2(像素→um，含旋转/各向异性), image_center_px/py }`
  - `TrayLayout{ rows, cols, pitch_um{x,y}, first_cell_offset_um{x,y}, order(行优先/蛇形) }`
  - `ScanPattern{ repeats_per_point=2, surrounding{ count=2, distance_um, angles/layout } }`
- **输出**：每个采集点一个目录（复用单点输出）+ 分层 manifest（晶片 → 样品中心 → 各点：像素/位移台坐标、重复次数、状态、路径）。可中断/可恢复/可审计（spec §17）。默认 csv/json；与 MAPS `.tdms` 是否互通待定（§5）。
- **可立刻开发/测试（纯逻辑，macOS）**：掩码→中心提取、像素→位移台仿射换算、样品盘几何→晶片中心偏移、扫描点图案生成、嵌套扫描编排（注入 fake stage/光源/相机 + dry-run）、manifest。**要上机（推迟）**：真实标定采数、激光斑像素确认、各物镜标定、真实 CCD 整片成像。
- **新依赖待定**：掩码连通域/质心提取可能需要 `numpy`（整片 CCD 图像较大，纯 stdlib 偏慢）；引入前需确认（当前项目仅 stdlib + pyyaml + pyserial + pytest）。

### M3 采集后处理增强
- 峰检测、基线校正、自动曝光、批量任务调度。纯数据处理，离线可验收，不涉真机安全。
- 自动曝光需要相机反馈回路，先在 simulated 后端验证收敛逻辑。

### M4 daemon / session 模式
- `ramanctl shell` 或 daemon，跨命令保留 DLL handle / 串口连接，供 Agent 长会话。
- **不得破坏现有无状态命令**；session 必须可选；连接生命周期、超时、异常重置要显式管理。

### M5 Agent tool schema + 权限系统
- 把 CLI 能力暴露为 Agent 可调用工具 schema，带权限分级。
- Agent **不得**直接碰协议字符串/native symbol，不得绕过安全层开激光/归零/长距离移动（spec §17）。

### M6 厂家 HTTP 光源后端
- 作为 M1 的同接口替代后端（typed `LightController` 方法），等厂家 API 上线。
- **同样的安全约束**：5.0 V 上限、通道映射、状态读回、dry-run；不能读回电压和输出状态则不得进入 `on_confirmed`；不得透传任意 HTTP 命令。

---

## 5. 开工前必须回答的待确认事项（spec §16）

这些**阻塞真机验收**或后续里程碑实现，但**不阻塞 dry-run/simulated 开发**。M1 上机前需老师/厂家确认，M2 上机前需完成位移台标定：

1. **光源（阻塞 M1 真机）**：白光/激光各接哪个 PWM 通道；实际 COM 口、站号；默认频率/占空比；输出电压是否全通道共享；激光安全联锁能否软件读取；数控电源输出端是否接负载、接线是否确认安全。
2. **激光功率控制机制（新发现，阻塞"自动调功率"）**：现场 SOP（[`docs/lab-sop-pl-mapping-zolix-ocr.md`](../../lab-sop-pl-mapping-zolix-ocr.md) §2）显示激光**功率**由 MAPS `Laser Power Adjust` 旋转**半波片**调节、输入数值功率；而 `Laser on/off` 是 Mode 面板开关。即开/关与功率可能是两套机制：开/关或走 PWM，功率走半波片。**待确认**：M1 的 PWM `laser_on/off` 是否对应 Mode 面板开关；功率究竟由半波片还是 PWM duty 控制。结论将决定 `set_intensity_percent` 如何建模（当前 PWM 后端刻意不实现它）。M1 已写的开关+联锁逻辑不受影响。
3. **像素↔位移台标定与物镜倍率（阻塞 M2 真机定点）**：M2 把识别给的**像素坐标**换算成位移台坐标，需要标定（um/px、图像中心↔位移台参考点、可能含旋转）；标定随**物镜倍率**变化（SOP §1 有物镜切换），必须按当前倍率取标定。如何获得标定（移动已知距离反推）需上机确定。
4. **位移台（阻塞 M2 真机）**：实际分辨率（丝杆导程、减速比）、轴方向是否与 PDF 示例一致。
5. **识别掩码的形式（不阻塞 M2 开发）**：冯博士只给识别后的图像/掩码，**中心提取由我们做**。需确认掩码形式（二值 mask / 标签图 / 画框 RGB），先按二值/标签 mask 开发，代码到了再对齐。
6. **测量点 = 图像中心 = 激光斑？（阻塞 M2 真机定点）**：确认 CCD 图像中心对应的就是激光测量点（SOP 第 2 步"激光圆圈在视场中心"），否则要把激光斑像素作为标定的一部分单独确定。
7. **样品盘几何（阻塞 M2 真机）**：行列数、格子间距、home 到第一个晶片中心的偏移、扫描顺序——需测量/确认填入 `TrayLayout`。
8. **周围 2 点的图案参数（M2 细节）**：与老师确认默认距离/方向（参数化，先给个默认值）。
9. **图像处理依赖**：掩码→质心是否引入 `numpy`（整片图像较大）；引入前确认。
10. **扫描输出格式**：默认 csv/json；是否需与 MAPS `.tdms` 互通待定。
11. **HTTP 后端（阻塞 M6）**：厂家 API 端口、命令字符串、状态读取能力、错误返回格式。
12. **现场核对**：MAPS 当前电脑的串口号、DLL 路径、光源控制方式与本仓库假设是否一致。

---

## 6. 建议的立即下一步

1. 写 M2 样品中心定点扫描的 task-by-task TDD 实现计划（中心点列表契约 + 像素↔位移台标定 + 逐点单点测量 + manifest；用手填列表做夹具）。
2. 向老师/厂家收集 §5 的待确认信息（尤其 §5.1 光源接线、§5.2 激光功率机制、§5.4 位移台标定）；这些不阻塞 simulated 开发，但会阻塞真机验收和"自动调激光功率"。
3. M2 完成后再决定 M3 与 M4 的先后（若先要数据质量，优先 M3；若先要 Agent 长会话，优先 M4）。
