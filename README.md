# 实验室 Raman/PL 自动化平台资料仓库

本仓库用于沉淀实验室 Raman/PL 自动化项目的原始硬件资料、老师整理的操作流程，以及后续软件开发规格。

当前阶段目标是打通自动化瓶颈：优先封装底层硬件控制能力，提供可脚本调用的 Python API 和 CLI，再为后续 AI Agent 实现完全自动化提供稳定、安全、可审计的接口。

## 目录说明

- `docs/superpowers/specs/`
  - 自动化平台规格文档。后续 Agent 开发应优先阅读这里。
- `自动化主要流程.docx`
  - 老师整理的 MAPS/WayneLabs 人工操作流程。
- `Waynelabs SDK Instructions.pdf`
  - WayneLabs 电动位移台和电动光路组件串口通信说明。
- `光谱议控制SDK-32&64bit-20250429/`
  - Zolix 光谱仪/单色仪 SDK、驱动、C++/LabVIEW/Python Demo。
- `DField-VS-A4-SDK-20250619/`
  - DField-VS-A4 CCD/相机探测器 SDK 和 Demo。

## 当前进度（2026-06-13）

- Phase 1 MVP **代码已完成并合并到 `main`**（commit `36518da`、`caa3429`）：`ramanctl` CLI、dry-run/simulated 模式、WayneLabs/Zolix/DField 适配器、单点 Raman/PL 工作流、安全校验。
- Phase 2 M1 **真实 PWM 光源后端已完成并合并到 `main`**：Modbus RTU raw 协议、`pwm_modbus` 配置解析、`PwmModbusLight` 读回确认安全序列、real-mode factory dispatch、硬件验收清单。
- 测试全绿（296 passed），默认 dry-run 单点工作流可输出完整动作序列。
- **仅剩真机验收未执行**：Phase 1 硬件验收见 `docs/phase1-hardware-acceptance.md`；Phase 2 M1 PWM 光源硬件验收见 `docs/phase2-hardware-acceptance.md`。两者都需在实验室 Windows 64 位机器上执行。
- 下一步：准备 Phase 2 M2 Mapping 区域扫描工作流 + CLI。

## 开发入口

第一版可执行规格文档：

- `docs/superpowers/specs/2026-06-04-lab-automation-platform-design.md`

该文档明确了 Phase 1 范围：

- Python 包和 `ramanctl` CLI。
- dry-run/simulated 模式。
- WayneLabs 位移台串口封装。
- Zolix 光谱仪 DLL 封装。
- DField 相机 DLL 封装。
- 单点 Raman/PL 测量工作流。

真实 PWM 光源控制器接入已作为 Phase 2 M1 完成。Mapping、采集后处理增强、Agent tool schema、daemon/session 模式和厂家 HTTP 光源后端属于后续 Phase 2 里程碑。

## 仓库约定

- `tmp/`、`output/`、`state/`、`logs/` 是生成物或运行时状态，不进入 Git。
- 厂家 SDK 和原始文档作为项目资料保留在仓库中。
- 后续实现真实硬件控制时，默认先支持 dry-run，再上机验证。
- 真实硬件动作必须保留日志、元数据和安全确认。
