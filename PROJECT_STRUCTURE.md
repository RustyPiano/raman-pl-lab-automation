# 项目目录结构

本文档说明项目的目录组织和文件用途。

## 目录树

```
自主实验平台/
├── src/                          # Python 源代码
│   └── lab_auto/                 # 主包
│       ├── api/                  # FastAPI 后端
│       ├── devices/              # 硬件设备驱动
│       ├── workflow/             # 工作流逻辑
│       └── config.py             # 配置加载
│
├── frontend/                     # React 前端
│   ├── src/                      # 前端源代码
│   │   ├── api/                  # API 客户端
│   │   ├── components/           # React 组件
│   │   ├── stores/               # Zustand 状态管理
│   │   └── views/                # 页面视图
│   ├── public/                   # 静态资源
│   └── package.json              # Node.js 依赖
│
├── docs/                         # 文档
│   ├── windows/                  # Windows 部署文档
│   ├── superpowers/              # 规格文档
│   ├── phase1-hardware-acceptance.md
│   └── phase2-hardware-acceptance.md
│
├── scripts/                      # 脚本和工具
│   ├── start_api.sh              # macOS 后端启动
│   ├── start_frontend.sh         # macOS 前端启动
│   ├── start_api.bat             # Windows 后端启动
│   ├── start_frontend.bat        # Windows 前端启动
│   ├── install_windows.bat       # Windows 自动安装
│   ├── check_ports.bat           # COM 端口检测
│   ├── test_api.py               # API 测试脚本
│   └── demo_api.py               # API 演示脚本
│
├── configs/                      # 配置文件
│   ├── devices.yaml              # 设备配置 (gitignored)
│   ├── devices.example.yaml      # 设备配置模板
│   └── *.yaml                    # 工作流配置 (gitignored)
│
├── vendor/                       # 第三方 SDK
│   └── nncamsdk.20240325/        # NNCam 相机 SDK
│
├── tests/                        # 测试代码
│   ├── test_*.py                 # 单元测试
│   └── integration/              # 集成测试
│
├── tmp/                          # 临时文件 (gitignored)
├── output/                       # 输出数据 (gitignored)
├── state/                        # 运行时状态 (gitignored)
├── logs/                         # 日志文件 (gitignored)
├── .agents/                      # Claude 子代理缓存 (gitignored)
│
└── 根目录文件
    ├── README.md                 # 项目主文档
    ├── CHANGELOG.md              # 变更日志
    ├── API_README.md             # FastAPI 使用文档
    ├── FASTAPI_IMPLEMENTATION_SUMMARY.md  # 后端实现总结
    ├── PROJECT_STRUCTURE.md      # 本文档
    ├── .gitignore                # Git 忽略规则
    ├── requirements.txt          # Python 依赖
    └── pyproject.toml            # Python 项目配置
```

## 目录说明

### `/src/` - 源代码
- **lab_auto/api/** - FastAPI 后端实现
  - `main.py` - FastAPI 应用入口
  - `models.py` - Pydantic 数据模型
  - `task_queue.py` - 单线程任务队列
  - `websocket.py` - WebSocket 连接管理
  - `routers/` - API 路由模块
- **lab_auto/devices/** - 硬件设备适配器
- **lab_auto/workflow/** - 工作流编排逻辑

### `/frontend/` - 前端应用
- **src/** - React + TypeScript 源代码
- **node_modules/** - npm 依赖 (gitignored)
- **dist/** - 构建输出 (gitignored)

### `/docs/` - 文档
- **windows/** - Windows 部署相关文档（8 个文档）
- **superpowers/** - 规格文档和设计文档

### `/scripts/` - 脚本
- **启动脚本** - 一键启动后端和前端
- **安装脚本** - Windows 自动化安装
- **测试脚本** - API 测试和演示

### `/configs/` - 配置
- 设备配置 (devices.yaml)
- 工作流配置 (*.yaml)
- 所有 `.yaml` 文件默认 gitignored，使用 `.example.yaml` 作为模板

### `/vendor/` - 第三方 SDK
- NNCam 相机 SDK
- 其他硬件厂商 SDK

### `/tests/` - 测试
- 单元测试
- 集成测试
- 硬件验收测试

## 忽略的目录

以下目录在 `.gitignore` 中，不会提交到 Git：

- `tmp/` - 临时文件
- `output/` - 实验数据输出
- `state/` - 运行时状态
- `logs/` - 日志文件
- `.agents/` - Claude 子代理缓存
- `node_modules/` - npm 依赖
- `dist/` - 前端构建输出
- `.venv/` - Python 虚拟环境
- `__pycache__/` - Python 缓存

## 快速导航

### 我想了解...

- **如何启动系统？** → 查看 [README.md](./README.md) 快速开始章节
- **API 接口文档？** → 查看 [API_README.md](./API_README.md)
- **Windows 部署？** → 查看 [docs/windows/WINDOWS_SETUP.md](./docs/windows/WINDOWS_SETUP.md)
- **前端开发？** → 查看 [frontend/README.md](./frontend/README.md)
- **变更历史？** → 查看 [CHANGELOG.md](./CHANGELOG.md)
- **目录结构？** → 你正在看它！

### 我想修改...

- **后端 API** → `src/lab_auto/api/`
- **前端界面** → `frontend/src/`
- **硬件驱动** → `src/lab_auto/devices/`
- **工作流逻辑** → `src/lab_auto/workflow/`
- **配置文件** → `configs/`

### 我想运行...

- **后端服务** → `./scripts/start_api.sh` (macOS) 或 `scripts\start_api.bat` (Windows)
- **前端服务** → `./scripts/start_frontend.sh` (macOS) 或 `scripts\start_frontend.bat` (Windows)
- **API 测试** → `python scripts/test_api.py`
- **完整演示** → `python scripts/demo_api.py`

## 文件命名约定

- **Python 文件** - 小写下划线：`task_queue.py`
- **TypeScript 文件** - PascalCase：`SinglePoint.tsx`
- **配置文件** - 小写连字符：`devices.yaml`
- **文档文件** - 大写下划线：`WINDOWS_SETUP.md`
- **脚本文件** - 小写下划线：`start_api.sh`

## 更新历史

- 2026-07-01: 项目目录整理，创建本文档
- 2026-07-01: Phase A Web 平台完成
- 2026-06-13: Phase 1 & Phase 2 M1 完成
