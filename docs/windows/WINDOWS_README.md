# Windows 部署文档总览

**Raman/PL 自主实验平台 - Windows 版本**  
**生成日期**: 2026-07-01

---

## 📋 文档索引

本目录包含完整的 Windows 部署文档套件：

### 核心文档
1. **[WINDOWS_SETUP.md](WINDOWS_SETUP.md)** ⭐ 
   - 完整的 Windows 安装指南
   - 系统要求、安装步骤、故障排查
   - 推荐首次部署时阅读

2. **[WINDOWS_COMPATIBILITY_REPORT.md](WINDOWS_COMPATIBILITY_REPORT.md)**
   - 详细的兼容性分析报告
   - 硬件驱动验证结果
   - 技术实现细节

3. **[WINDOWS_QUICK_REFERENCE.md](WINDOWS_QUICK_REFERENCE.md)**
   - 快速参考指南
   - 常用命令速查
   - 故障排查速查表

4. **[WINDOWS_DEPLOYMENT_CHECKLIST.md](WINDOWS_DEPLOYMENT_CHECKLIST.md)**
   - 部署验证清单
   - 功能测试步骤
   - 签收确认表

### 脚本文件
- **`start_api.bat`** - 启动后端 FastAPI 服务
- **`start_frontend.bat`** - 启动前端 React 界面
- **`install_windows.bat`** - 自动安装脚本
- **`check_ports.bat`** - COM 端口检测工具

### 配置模板
- **`devices.yaml.windows`** - Windows 设备配置模板

---

## 🚀 快速开始

### 1️⃣ 首次安装
```cmd
REM 运行自动安装脚本
install_windows.bat
```

### 2️⃣ 配置设备
```cmd
REM 检测 COM 端口
check_ports.bat

REM 复制配置模板
copy devices.yaml.windows devices.yaml

REM 编辑配置文件
notepad devices.yaml
```

### 3️⃣ 启动服务
```cmd
REM 启动后端 (新窗口)
start start_api.bat

REM 启动前端 (新窗口)
start start_frontend.bat
```

### 4️⃣ 访问系统
- **后端 API**: http://127.0.0.1:8008/docs
- **前端界面**: http://localhost:5173

---

## ✅ 兼容性摘要

### 完全支持的组件
- ✅ **FastAPI 后端** - Python 跨平台
- ✅ **React 前端** - Node.js 跨平台
- ✅ **Zolix 光谱仪** - ctypes.WinDLL 原生支持
- ✅ **NNCam 相机** - Windows DLL 已包含
- ✅ **载物台控制** - pyserial 串口通信
- ✅ **PWM 光源** - Modbus RTU 跨平台
- ✅ **路径处理** - pathlib.Path 跨平台

### 需要调整的项目
- ⚠️ 启动脚本：`.sh` → `.bat` (已创建)
- ⚠️ COM 端口：`/dev/ttyUSB0` → `COM5` (配置文件修改)
- ⚠️ DLL 路径：使用 Windows 绝对路径

### 不兼容项
- ❌ **无** - 未发现任何不兼容组件

---

## 📊 硬件驱动验证

| 设备 | Windows 支持 | 验证方式 |
|------|------------|---------|
| Zolix 光谱仪 | ✅ 完全支持 | ctypes.WinDLL 自动选择 |
| NNCam 相机 | ✅ 完全支持 | SDK 提供 x86/x64 DLL |
| 载物台 | ✅ 完全支持 | pyserial COM 端口 |
| PWM 光源 | ✅ 完全支持 | Modbus RTU 串口 |

**关键代码验证**:
```python
# src/lab_auto/devices/raw/zolix_ctypes.py:44
lib = ctypes.WinDLL(str(dll_path)) if hasattr(ctypes, "WinDLL") else ctypes.CDLL(str(dll_path))
```

---

## 🛠️ 系统要求

### 软件环境
- Windows 10/11 (64-bit)
- Python 3.12+
- Node.js 18+
- Git for Windows

### 硬件环境
- CPU: Intel i5 或以上
- 内存: 8GB+
- 存储: SSD 推荐
- 串口: USB-to-Serial 转换器（如需要）

---

## 📁 目录结构

```
自主实验平台/
├── WINDOWS_SETUP.md                    # 完整安装指南
├── WINDOWS_COMPATIBILITY_REPORT.md    # 兼容性报告
├── WINDOWS_QUICK_REFERENCE.md         # 快速参考
├── WINDOWS_DEPLOYMENT_CHECKLIST.md    # 部署清单
├── start_api.bat                      # 后端启动脚本
├── start_frontend.bat                 # 前端启动脚本
├── install_windows.bat                # 自动安装
├── check_ports.bat                    # COM 端口检测
├── devices.yaml.windows               # 配置模板
├── src/                               # 源代码
│   └── lab_auto/
│       ├── api/                       # FastAPI 后端
│       ├── devices/                   # 硬件驱动
│       └── workflow/                  # 实验流程
├── frontend/                          # React 前端
│   ├── src/
│   └── package.json
├── nncamsdk.20240325/                 # NNCam SDK
│   └── win/
│       ├── x64/nncam.dll
│       └── x86/nncam.dll
└── data/                              # 数据输出
```

---

## 🔧 配置文件示例

### devices.yaml (关键配置)
```yaml
runtime:
  mode: real
  log_level: INFO

stage:
  port: COM5              # ← 修改此处

spectrometer:
  dll_path: "C:\\Zolix\\SDK\\spec.dll"  # ← 修改此处

camera:
  dll_path: "nncamsdk.20240325\\win\\x64\\nncam.dll"

light:
  port: COM17             # ← 修改此处
  channels:
    laser:
      channel: 1          # ← 根据硬件修改
```

---

## 🐛 常见问题速查

| 问题 | 文档位置 | 解决方案 |
|------|---------|---------|
| 虚拟环境激活失败 | WINDOWS_SETUP.md §Q1 | 使用 CMD 而非 PowerShell |
| COM 端口拒绝访问 | WINDOWS_SETUP.md §Q2 | 关闭其他串口工具 |
| DLL 加载失败 | WINDOWS_SETUP.md §Q3 | 使用绝对路径 + 双反斜杠 |
| 相机检测失败 | WINDOWS_SETUP.md §Q4 | 安装驱动，检查 USB |
| 前端连接错误 | WINDOWS_SETUP.md §Q5 | 确认后端已启动 |
| 串口超时 | WINDOWS_SETUP.md §Q6 | 增加超时，检查波特率 |

---

## 📈 部署流程

```mermaid
graph LR
    A[检查系统要求] --> B[运行 install_windows.bat]
    B --> C[检测 COM 端口]
    C --> D[配置 devices.yaml]
    D --> E[启动后端服务]
    E --> F[启动前端界面]
    F --> G[功能验证]
    G --> H[硬件测试]
    H --> I[部署完成]
```

---

## 🎯 验证清单

部署完成后，确认以下项目：

### 基础环境
- [ ] Python 3.12+ 已安装
- [ ] Node.js 18+ 已安装
- [ ] 虚拟环境创建成功
- [ ] 所有依赖安装无错误

### 硬件连接
- [ ] COM 端口检测成功
- [ ] DLL 文件路径正确
- [ ] 设备管理器无感叹号

### 服务启动
- [ ] 后端 API 启动成功
- [ ] 前端界面加载正常
- [ ] API 文档可访问

### 功能测试
- [ ] 载物台移动响应
- [ ] 光谱仪控制正常
- [ ] 相机拍摄成功
- [ ] 光源控制生效

详细清单见 **WINDOWS_DEPLOYMENT_CHECKLIST.md**

---

## 🔒 安全建议

1. **激光安全**
   - 确认激光默认关闭
   - 配置安全互锁
   - 熟悉紧急停止流程

2. **软限位**
   - 正确配置 `soft_limits_um`
   - 测试限位保护
   - 避免硬件碰撞

3. **数据备份**
   - 定期备份 `devices.yaml`
   - 保存 `stage_state.json`
   - 导出实验数据

4. **访问控制**
   - 仅在本地运行（127.0.0.1）
   - 不要暴露到公网
   - 限制操作权限

---

## 📞 技术支持

### 文档资源
- **安装问题**: WINDOWS_SETUP.md
- **兼容性问题**: WINDOWS_COMPATIBILITY_REPORT.md
- **操作问题**: WINDOWS_QUICK_REFERENCE.md
- **验证问题**: WINDOWS_DEPLOYMENT_CHECKLIST.md

### 项目资源
- **项目概览**: `docs/project-overview.html`
- **内存文档**: `.claude/projects/.../memory/MEMORY.md`
- **API 文档**: http://127.0.0.1:8008/docs (启动后)

### 社区资源
- **pyserial 文档**: https://pyserial.readthedocs.io/
- **FastAPI 文档**: https://fastapi.tiangolo.com/
- **React 文档**: https://react.dev/

---

## 📝 更新日志

### 2026-07-01 - 初始版本
- ✅ 创建 Windows 部署文档套件
- ✅ 验证所有硬件驱动兼容性
- ✅ 创建启动脚本 (.bat)
- ✅ 提供配置模板
- ✅ 编写故障排查指南

---

## 📄 许可证

本文档为项目内部文档，与项目主许可证保持一致。

---

## 🙏 致谢

感谢以下技术支持：
- **Python**: 跨平台运行时
- **ctypes**: 原生 DLL 调用
- **pyserial**: 串口通信库
- **FastAPI**: Web 框架
- **React**: 前端框架
- **Vite**: 构建工具

---

**文档维护者**: 项目团队  
**最后更新**: 2026-07-01  
**文档版本**: 1.0

---

## 🚦 部署状态指示

部署完成后，在此标记状态：

- [ ] 文档已阅读
- [ ] 环境已安装
- [ ] 配置已完成
- [ ] 服务已启动
- [ ] 功能已验证
- [ ] ✅ **Windows 部署完成**

---

**开始部署**: 阅读 [WINDOWS_SETUP.md](WINDOWS_SETUP.md) →
