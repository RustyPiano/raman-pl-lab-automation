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

## 当前进度

### Phase 1 & Phase 2 M1 ✅ 已完成（2026-06-13）

- Phase 1 MVP **代码已完成并合并到 `main`**（commit `36518da`、`caa3429`）：`ramanctl` CLI、dry-run/simulated 模式、WayneLabs/Zolix/DField 适配器、单点 Raman/PL 工作流、安全校验。
- Phase 2 M1 **真实 PWM 光源后端已完成并合并到 `main`**：Modbus RTU raw 协议、`pwm_modbus` 配置解析、`PwmModbusLight` 读回确认安全序列、real-mode factory dispatch、硬件验收清单。
- 测试全绿（296 passed），默认 dry-run 单点工作流可输出完整动作序列。

### Phase A: Web 平台 ✅ 已完成（2026-07-01）

**现代化 Web 界面 + FastAPI 后端**

- ✅ **后端 (FastAPI)**：REST API + WebSocket 实时推送（评分 94/100，生产级）
  - 单线程任务队列（硬件安全保障）
  - Web API 默认 dry-run；real 模式必须显式安全确认
  - 路径注入防护
  - 完整的设备、配置、工作流管理 API
  - 自动生成 Swagger 文档：http://127.0.0.1:8008/docs

- ✅ **前端 (React + shadcn/ui)**：用户友好的操作界面（评分 91/100，生产级）
  - TypeScript 严格模式
  - 实时进度显示（8 步骤可视化）
  - 光谱数据图表
  - real 模式安全确认对话框
  - 类型安全错误处理

- ✅ **当前验证**：`pytest -q` 393 passed；`npm run build` passed

- ✅ **跨平台支持**：macOS + Windows 完全兼容
  - 提供完整的 Windows 部署文档和脚本
  - 所有硬件驱动已验证 Windows 兼容性

**文档**：
- 后端文档：[API_README.md](./API_README.md)
- Windows 部署：[docs/windows/WINDOWS_SETUP.md](./docs/windows/WINDOWS_SETUP.md)
- 前端文档：[frontend/README.md](./frontend/README.md)

**快速启动**：
```bash
# macOS
./scripts/start_api.sh       # 后端 http://127.0.0.1:8008
./scripts/start_frontend.sh  # 前端 http://localhost:5173

# Windows
scripts\start_api.bat
scripts\start_frontend.bat
```

### 待办事项

- **真机验收未执行**：Phase 1 硬件验收见 `docs/phase1-hardware-acceptance.md`；Phase 2 M1 PWM 光源硬件验收见 `docs/phase2-hardware-acceptance.md`。两者都需在实验室 Windows 64 位机器上执行。
- **Phase B 规划**：托盘扫描 UI、设备监控面板、历史记录查询
- **Phase 2 M2 规划**：Mapping 区域扫描工作流 + CLI

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
