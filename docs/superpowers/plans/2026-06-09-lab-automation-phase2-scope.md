# Lab Automation Phase 2 Scope & Sequencing Plan

> **Status (2026-06-09): Planning. No Phase 2 code written yet.**
> Phase 1 MVP is code-complete and merged to `main` (`36518da`, `caa3429`);
> 235 tests pass; the only outstanding Phase 1 gate is the on-hardware
> acceptance in [`docs/phase1-hardware-acceptance.md`](../../phase1-hardware-acceptance.md),
> deliberately deferred until all development is finished. This document plans
> Phase 2: what we build, in what order, under what contracts, and which
> open questions must be answered before any **real-hardware** action ships.

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

| # | 里程碑 | 依赖 | 真机前置（上机才确认） |
|---|--------|------|------------------------|
| **M1** | 真实 PWM 光源后端（Modbus RTU） | 无（扩展现有 light 分层） | 通道映射、COM 口、站号、频率/占空比、接线安全、联锁可读性 |
| **M2** | Mapping 区域扫描工作流 + CLI | M1 可选；依赖 stage 安全状态机（已存在） | 位移台分辨率/轴方向标定 |
| **M3** | 采集后处理增强（峰检测、基线校正、自动曝光、批量调度） | M2（批量调度复用 Mapping 网格） | 无（纯数据处理，可离线验收） |
| **M4** | daemon / session 模式（`ramanctl shell` 或 daemon） | M1–M3 适配器稳定 | 无 |
| **M5** | Agent tool schema + 权限系统 | M1–M4（暴露稳定能力） | 无 |
| **M6** | 厂家 HTTP 光源后端（M1 的替代/补充） | M1；厂家 API 上线 | HTTP 端口、命令字符串、状态读回、错误格式 |

**建议先做 M1。** 它风险最高、最能解锁"全自动开关激光"的瓶颈，且与现有 `ManualLight` 分层无缝衔接；M6 是它的同接口替代后端，等厂家 API 上线再做。

---

## 3. M1：真实 PWM 光源后端（Modbus RTU）—— 详细契约

这是 Phase 2 安全最关键的一块，spec §6.5 / §12.2 / §12.3 已给出完整协议和联锁要求。下面是落地契约。

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

### M2 Mapping 区域扫描
- 新增 `src/lab_auto/workflow/mapping.py` + `ramanctl mapping` 命令组。
- **硬前置**：X/Y 轴均为 `homed` 或 `user_zeroed`（spec §12.1）；`unknown` 禁止 Mapping。复用现有 stage 状态机与软限位。
- 网格定义、逐点测量复用 M1 光源 + 现有单点工作流；输出每点目录 + 汇总 manifest；可中断/可恢复/可审计（spec §17）。

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

这些**阻塞真机实现/验收**，但**不阻塞 dry-run/simulated 开发**。M1 开发可立即开始；上机前需老师/厂家确认：

1. **光源（阻塞 M1 真机）**：白光/激光各接哪个 PWM 通道；实际 COM 口、站号；默认频率/占空比；输出电压是否全通道共享；激光安全联锁能否软件读取；数控电源输出端是否接负载、接线是否确认安全。
2. **位移台（阻塞 M2 真机）**：实际分辨率（丝杆导程、减速比）、轴方向是否与 PDF 示例一致。
3. **样品识别（阻塞 M2 自动定位）**：与冯博士确定输入/输出/标定方式/失败策略（spec §16.11）。
4. **HTTP 后端（阻塞 M6）**：厂家 API 端口、命令字符串、状态读取能力、错误返回格式。
5. **现场核对**：MAPS 当前电脑的串口号、DLL 路径、光源控制方式与本仓库假设是否一致。

---

## 6. 建议的立即下一步

1. **锁定 M1 为首个开工项**，按本文件 §3 契约写 M1 的 task-by-task TDD 实现计划（类似 Phase 1 的 `phase1-mvp` plan）。
2. 向老师/厂家收集 §5.1 的光源待确认信息（不阻塞开发，但越早越好，便于后续真机验收）。
3. M1 开发完成后再决定 M2 与 M3 的先后（若近期要做面扫描，优先 M2；若先要数据质量，优先 M3）。
