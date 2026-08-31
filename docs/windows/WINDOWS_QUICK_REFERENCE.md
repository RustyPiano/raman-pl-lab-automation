# Windows 快速参考指南

## 快速启动

### 首次安装
```cmd
install_windows.bat
```

### 启动服务
```cmd
start_api.bat       # 后端 → http://127.0.0.1:8008
start_frontend.bat  # 前端 → http://localhost:5173
```

### 检查 COM 端口
```cmd
check_ports.bat
```

---

## 常用命令

### Python 环境
```cmd
# 激活虚拟环境
.venv\Scripts\activate.bat

# 安装新依赖
pip install <package_name>

# 运行命令行工具
ramanctl status
ramanctl move --axis x --distance 1000
```

### 前端开发
```cmd
cd frontend
npm run dev      # 开发服务器
npm run build    # 生产构建
npm run lint     # 代码检查
```

### 数据管理
```cmd
# 查看输出数据
explorer data\

# 清空缓存
rmdir /S /Q data\stage_state.json
```

---

## 配置文件速查

### devices.yaml 关键配置
```yaml
# 串口设备
stage:
  port: COM5          # ← 修改此处

light:
  port: COM17         # ← 修改此处

# DLL 路径
spectrometer:
  dll_path: "C:\\Zolix\\SDK\\spec.dll"  # ← 修改此处

camera:
  dll_path: "nncamsdk.20240325\\win\\x64\\nncam.dll"  # ← 修改此处
```

---

## 故障排查

| 问题 | 快速解决 |
|------|---------|
| 虚拟环境激活失败 | 使用 CMD（不是 PowerShell） |
| COM 端口拒绝访问 | 关闭其他串口工具，重启端口 |
| DLL 找不到 | 使用绝对路径 + 双反斜杠 |
| 相机检测失败 | 安装驱动，检查 USB 连接 |
| 后端无法启动 | 检查端口 8008 是否被占用 |
| 前端连接失败 | 确认后端已启动 |

---

## 端口占用检查
```cmd
# 查看端口 8008
netstat -ano | findstr :8008

# 结束进程（PID 替换为实际值）
taskkill /F /PID <PID>
```

---

## COM 端口映射

根据 `lab-hardware-com-map.md` 配置：

| 设备 | COM 端口 | 波特率 |
|------|---------|--------|
| 载物台 | COM5 | 9600 |
| PWM 光源 | COM17 | 9600 |
| Zolix 光谱仪 | USB | - |

---

## 性能优化清单

- [ ] Windows Defender 排除项目目录
- [ ] 增加 COM 端口缓冲区（设备管理器）
- [ ] 关闭不必要的后台程序
- [ ] 设置进程高优先级

---

## 文件说明

| 文件 | 用途 |
|------|------|
| `start_api.bat` | 启动后端服务 |
| `start_frontend.bat` | 启动前端界面 |
| `install_windows.bat` | 自动安装脚本 |
| `check_ports.bat` | 检测 COM 端口 |
| `WINDOWS_SETUP.md` | 完整安装指南 |
| `WINDOWS_COMPATIBILITY_REPORT.md` | 兼容性分析报告 |

---

## API 快速测试

### 使用浏览器
访问 http://127.0.0.1:8008/docs 查看交互式 API 文档

### 使用 curl (Git Bash)
```bash
# 获取系统状态
curl http://127.0.0.1:8008/api/status

# 移动载物台
curl -X POST http://127.0.0.1:8008/api/stage/move \
  -H "Content-Type: application/json" \
  -d '{"axis": "x", "distance_um": 1000}'
```

### 使用 PowerShell
```powershell
# 获取系统状态
Invoke-WebRequest -Uri http://127.0.0.1:8008/api/status

# 移动载物台
$body = @{axis="x"; distance_um=1000} | ConvertTo-Json
Invoke-WebRequest -Uri http://127.0.0.1:8008/api/stage/move `
  -Method POST -Body $body -ContentType "application/json"
```

---

## 日志调试

### 启用详细日志
修改 `devices.yaml`:
```yaml
runtime:
  log_level: DEBUG  # INFO | DEBUG | WARNING | ERROR
```

### 保存日志到文件
```cmd
start_api.bat > logs\api.log 2>&1
```

### 实时查看日志
```cmd
type logs\api.log
```

---

## 更新项目

### 拉取最新代码
```cmd
git pull origin main

# 更新 Python 依赖
.venv\Scripts\activate.bat
pip install -e . --upgrade

# 更新前端依赖
cd frontend
npm install
```

---

## 安全建议

1. **不要以管理员身份运行**（除非必要）
2. **定期备份配置文件** (`devices.yaml`, `stage_state.json`)
3. **检查 COM 端口权限**（避免冲突）
4. **关闭防火墙警告**（仅限本地开发）

---

## 硬件连接检查清单

启动前确认：
- [ ] Zolix 光谱仪 USB 已连接
- [ ] 载物台串口线已插入
- [ ] PWM 光源控制器已通电
- [ ] NNCam 相机 USB 已连接
- [ ] 所有设备在设备管理器中无感叹号

---

## 技术支持

- **完整文档**: `WINDOWS_SETUP.md`
- **兼容性报告**: `WINDOWS_COMPATIBILITY_REPORT.md`
- **项目文档**: `docs/project-overview.html`
- **内存文档**: `.claude/projects/.../memory/MEMORY.md`

---

**快速诊断命令**:
```cmd
# 一键检查环境
.venv\Scripts\activate.bat && python -c "import sys; import serial; import yaml; import fastapi; print('✓ All dependencies OK')"
```

**生成时间**: 2026-07-01
