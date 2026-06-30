# 变更日志

本文档记录项目的重要变更和里程碑。

## [Phase A] - 2026-07-01

### 新增 - Web 平台

#### 后端 (FastAPI)
- ✅ 创建 FastAPI 应用框架 (`src/lab_auto/api/`)
- ✅ REST API 端点：
  - `/api/devices/*` - 设备管理和状态查询
  - `/api/configs/*` - 配置文件管理
  - `/api/workflow/*` - 工作流执行和任务管理
  - `/api/workflow/ws/jobs/{job_id}` - WebSocket 实时进度推送
- ✅ 单线程任务队列（`ThreadPoolExecutor(max_workers=1)`）
- ✅ Pydantic 数据模型和类型安全
- ✅ WebSocket ConnectionManager（多客户端支持）
- ✅ 自动生成 Swagger 文档

#### 前端 (React + shadcn/ui)
- ✅ React 19 + TypeScript + Vite 项目初始化
- ✅ shadcn/ui 组件集成（9 个组件）
- ✅ Zustand 状态管理
- ✅ 核心页面：
  - 单点测量（配置选择、YAML 参数、实时进度）
  - 托盘扫描（占位）
  - 设备监控（占位）
  - 历史记录（占位）
- ✅ 实时功能：
  - WebSocket 自动重连（指数退避）
  - 进度条和步骤显示
  - 日志窗口（最多 99 条）
  - Toast 通知系统
- ✅ 光谱图表（Recharts）
- ✅ 安全确认对话框（real 模式激光操作）

#### 跨平台支持
- ✅ Windows 兼容性全面验证
- ✅ Windows 部署文档（8 个文档）
- ✅ Windows 启动脚本（`.bat` 文件）
- ✅ 设备配置模板（`devices.yaml.windows`）
- ✅ COM 端口检测工具

#### 文档
- ✅ `API_README.md` - FastAPI 使用文档
- ✅ `FASTAPI_IMPLEMENTATION_SUMMARY.md` - 实现总结
- ✅ `frontend/README.md` - 前端开发指南
- ✅ `frontend/PROJECT_SUMMARY.md` - 前端架构说明
- ✅ `frontend/TESTING.md` - 测试指南
- ✅ Windows 部署文档套件（8 个文档）
- ✅ `CHANGELOG.md` - 本文档

#### 测试脚本
- ✅ `test_api.py` - 后端 API 测试
- ✅ `demo_api.py` - API 完整功能演示
- ✅ `src/lab_auto/api/test_critical_fixes.py` - 关键问题验证

### 修复 - Critical 问题

#### 后端修复
- ✅ 异步事件循环冲突：移除所有 `asyncio.run()` 调用
- ✅ 单线程保证：添加 `ThreadPoolExecutor(max_workers=1)`
- ✅ 路径注入防护：使用 `Path.resolve()` + `relative_to()` 强化安全

#### 前端修复
- ✅ TypeScript 严格模式：启用 `strict: true`
- ✅ 类型安全错误处理：添加 `getErrorMessage()` 工具函数
- ✅ WebSocket URL 构造：支持 `VITE_WS_HOST` 环境变量
- ✅ UI 组件完整性：安装所有 shadcn/ui 组件
- ✅ 前后端 API 契约对齐：前端发送 `config_path`，使用后端返回的任务 `id`
- ✅ WebSocket 代理路径修复：开发模式通过 `/api/workflow/ws/jobs/{job_id}` 转发
- ✅ Tailwind CSS v4 构建修复：使用 `@tailwindcss/postcss`

#### 安全修复
- ✅ Web API 默认 `dry_run`，不再默认进入 real 模式
- ✅ real 模式必须显式传入 `confirm_real=true`
- ✅ `TaskQueue` 层也拒绝未确认的 real 模式任务，防止绕过路由直接入队

### 代码质量
- 默认测试入口：`pytest -q` 只收集 `tests/`
- 当前验证：`pytest -q` 393 passed；`npm run build` passed

### 技术栈
- 后端：FastAPI + asyncio + ThreadPoolExecutor
- 前端：React 19 + TypeScript + Vite + shadcn/ui + Zustand + Recharts
- 通信：REST API + WebSocket
- 平台：macOS + Windows

---

## [Phase 2 M1] - 2026-06-13

### 新增
- ✅ 真实 PWM 光源后端
- ✅ Modbus RTU raw 协议
- ✅ `pwm_modbus` 配置解析
- ✅ `PwmModbusLight` 读回确认安全序列
- ✅ real-mode factory dispatch
- ✅ 硬件验收清单

---

## [Phase 1 MVP] - 2026-06-13

### 新增
- ✅ `ramanctl` CLI
- ✅ dry-run/simulated 模式
- ✅ WayneLabs 位移台适配器
- ✅ Zolix 光谱仪适配器
- ✅ DField 相机适配器
- ✅ 单点 Raman/PL 工作流
- ✅ 安全校验

### 测试
- ✅ 296 个测试全部通过

---

## 待办事项

### Phase B (规划中)
- ⏳ 托盘扫描 UI 实现
- ⏳ 设备监控面板
- ⏳ 历史记录查询
- ⏳ 批量任务管理

### Phase C (规划中)
- ⏳ 用户认证系统
- ⏳ 任务持久化（数据库）
- ⏳ 实时光谱预览
- ⏳ 性能优化

### 硬件验收
- ⏳ Phase 1 硬件验收（见 `docs/phase1-hardware-acceptance.md`）
- ⏳ Phase 2 M1 PWM 光源验收（见 `docs/phase2-hardware-acceptance.md`）
- 要求：在实验室 Windows 64 位机器上执行

### Phase 2 M2 (规划中)
- ⏳ Mapping 区域扫描工作流
- ⏳ 扫描模式 CLI

---

## 版本说明

- **Phase A**: Web 平台核心功能（FastAPI + React）
- **Phase 1**: CLI 和底层硬件封装
- **Phase 2**: 真实硬件集成和高级功能
- **Phase 3**: AI Agent 自动化集成（未来）
