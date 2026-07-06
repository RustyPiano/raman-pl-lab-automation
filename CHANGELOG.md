# 变更日志

本文档记录项目的重要变更和里程碑。

## [P0 安全修复] - 2026-07-06

基于全面盲点审计（5 维度并行审计）的激光安全闭环修复。**这批修复完成前不建议上真机跑 real 模式。**

### 激光安全闭环
- ✅ 上电安全复位：`create_light` 打开传输后立即全通道关断 + 读回确认（崩溃后重启不再对残留激光状态毫无感知）
- ✅ API 启动/优雅关闭时执行 best-effort 光源复位；注册 `atexit` 兜底关断
- ✅ 新增 `POST /api/emergency-stop`：取消所有任务 + 绕过（可能被卡死的）硬件执行器直接强制关灯，响应如实报告 `laser_off` 状态
- ✅ 移除 `POST /api/devices/light/on`（无认证裸激光开启端点是 CSRF 攻击面）

### 真实的任务取消
- ✅ 协作式取消：per-job `threading.Event` + 工作流检查点（配置前/采背景前/开激光前/采样前/每个扫描点前）
- ✅ 新增 `stopping` 过渡状态：停止请求发出后如实显示"正在停止"，工作流安全收尾（强制关激光）后才报 `stopped`
- ✅ worker 不再把 stopped 覆写成 completed；异常路径不再让任务"人间蒸发"
- ✅ 前端停止按钮诚实化：显示"正在停止（等待硬件安全收尾）"，保持 WebSocket 直到后端确认

### 堵死 input() 挂死链
- ✅ API 拒绝 `real + manual light`（终端交互确认会挂死服务器线程）
- ✅ API 拒绝 `confirm_real=true` + 非 real 模式（router 与 TaskQueue 双层防御）

### 设备端点重写
- ✅ 全部硬件端点移出事件循环线程；任务运行中返回 409 而非争抢串口
- ✅ 光源状态查询改为只读寄存器回读（`read_hardware_state`），收尾不再有关灯副作用
- ✅ 修正方法名错配（原端点调用不存在的 `turn_on/turn_off/is_on`）

### 串口/Modbus 健壮性
- ✅ Modbus 失步自愈：每次写前清输入缓冲；读/解析失败 flush 后重试一次；`laser_off` 失败整体重试（一个杂散字节不再导致"激光关不掉"）
- ✅ `_read_exact` 每次迭代检查 deadline（慢滴字节不再无限拖延）
- ✅ 位置台账两阶段写：移动/home 前先落盘 in-flight 标记（中途崩溃 → 该轴强制 UNKNOWN 需重新 home）；台账原子写
- ✅ `home_direction` 配置校验：撞错方向限位记为原点会反转坐标系，现在可配置安全方向并拒绝不符调用

### 参数硬上限
- ✅ `exposure_ms` ≤ 60s、`frames` ≤ 1000（多打一个 0 不再变成 2.8 小时激光照射）
- ✅ `burn_threshold` 必须 > 0（0 会把所有点标为烧毁）

### 验证
- `pytest -q`：462 passed, 2 skipped（基线 391）；`npm run build` passed
- 新增测试约 70 个：取消语义、失步自愈、台账崩溃安全、紧急停止、启动复位等

---

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
