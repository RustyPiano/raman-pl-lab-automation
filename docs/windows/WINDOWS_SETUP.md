# Windows 部署指南

**适用系统**: Windows 10/11 (64-bit)  
**项目**: Raman/PL 自主实验平台

---

## 系统要求

### 软件环境
- **Python 3.12+** (推荐 3.12 或 3.13)
  - 下载: https://www.python.org/downloads/
  - 安装时勾选 "Add Python to PATH"
- **Node.js 18+** (推荐 LTS 版本)
  - 下载: https://nodejs.org/
- **Git for Windows**
  - 下载: https://git-scm.com/download/win

### 硬件要求
- **串口设备**:
  - Zolix 光谱仪 (USB/RS232)
  - WayneLabs 载物台 (COM 端口)
  - PWM 光源控制器 (Modbus RTU)
- **相机**: NNCam 兼容相机
- **推荐配置**:
  - CPU: Intel i5 或以上
  - 内存: 8GB+
  - 存储: SSD（用于数据输出）

---

## 安装步骤

### 1. 克隆项目
```cmd
git clone <repository_url>
cd 自主实验平台
```

### 2. 安装 Python 依赖
```cmd
REM 创建虚拟环境
python -m venv .venv

REM 激活虚拟环境
.venv\Scripts\activate.bat

REM 安装核心依赖
pip install --upgrade pip
pip install -e .

REM 安装 Web 服务依赖
pip install uvicorn fastapi pydantic

REM 安装图像处理依赖（用于相机和识别）
pip install pillow
```

### 3. 安装前端依赖
```cmd
cd frontend
npm install
cd ..
```

### 4. 配置硬件设备

#### 4.1 识别 COM 端口
打开设备管理器（`devmgmt.msc`），在"端口(COM 和 LPT)"下查看：
- Zolix 光谱仪: 例如 `COM3`
- 载物台: 例如 `COM5`
- PWM 光源: 例如 `COM17`

#### 4.2 配置 DLL 路径
找到硬件厂商提供的 DLL 文件：
- **Zolix 光谱仪**: 通常在厂商 SDK 目录（如 `C:\Zolix\SDK\spec.dll`）
- **NNCam 相机**: 已包含在项目中 `nncamsdk.20240325\win\x64\nncam.dll`

#### 4.3 创建配置文件
复制示例配置：
```cmd
copy config\devices.yaml.example config\devices.yaml
```

编辑 `config\devices.yaml`：
```yaml
runtime:
  mode: real  # real | simulated | dry_run
  log_level: INFO

stage:
  type: waynelabs_linear
  port: COM5  # ← 修改为实际 COM 端口
  baudrate: 9600
  resolution_um:
    x: 0.15625
    y: 0.15625
    z: 0.15625
  default_speed: 3000
  soft_limits_um:
    x: [-50000.0, 50000.0]
    y: [-50000.0, 50000.0]
    z: [-10000.0, 10000.0]
  state_file: data/stage_state.json
  max_unknown_move_um: 1000.0

spectrometer:
  type: zolix
  dll_path: "C:\\Zolix\\SDK\\spec.dll"  # ← 修改为实际路径
  usb_mode: true

camera:
  type: nncam
  dll_path: "nncamsdk.20240325\\win\\x64\\nncam.dll"  # 或绝对路径

light:
  type: pwm_modbus  # 或 manual
  manual_light_control: false
  port: COM17  # ← 修改为实际 COM 端口
  station_id: 1
  baudrate: 9600
  max_output_voltage_v: 5.0
  required_output_voltage_v: 3.3
  channels:
    laser:
      channel: 1
      frequency_hz: 1000
      duty_percent: 50.0
      default_off_required: true
    led:
      channel: 2
      frequency_hz: 1000
      duty_percent: 30.0
      default_off_required: false
```

---

## 启动服务

### 方法 1: 使用启动脚本（推荐）

#### 启动后端 API
双击 `start_api.bat` 或在命令行运行：
```cmd
start_api.bat
```
访问: http://127.0.0.1:8008/docs

#### 启动前端界面
双击 `start_frontend.bat` 或在命令行运行：
```cmd
start_frontend.bat
```
访问: http://localhost:5173

### 方法 2: 手动启动

#### 后端
```cmd
.venv\Scripts\activate.bat
set PYTHONPATH=src
uvicorn lab_auto.api.main:app --host 127.0.0.1 --port 8008 --reload
```

#### 前端
```cmd
cd frontend
npm run dev
```

---

## 验证安装

### 1. 检查 Python 依赖
```cmd
.venv\Scripts\activate.bat
python -c "import serial; import yaml; print('Dependencies OK')"
```

### 2. 检查 COM 端口
```cmd
python -m serial.tools.list_ports
```
输出示例：
```
COM3 - USB Serial Port
COM5 - USB Serial Port
COM17 - USB Serial Port
```

### 3. 测试 API
打开浏览器访问 http://127.0.0.1:8008/docs，应看到 FastAPI 文档页面。

### 4. 测试硬件连接
```cmd
.venv\Scripts\activate.bat
ramanctl status
```
应显示各设备状态（如已配置）。

---

## 常见问题

### Q1: 虚拟环境激活失败
**错误**: `因为在此系统上禁止运行脚本`

**解决**:
1. 以管理员身份打开 PowerShell
2. 运行: `Set-ExecutionPolicy RemoteSigned -Scope CurrentUser`
3. 确认后重新激活虚拟环境

或使用 CMD（不是 PowerShell）运行 `.venv\Scripts\activate.bat`

### Q2: COM 端口访问被拒绝
**错误**: `PermissionError: [Errno 13] Permission denied: 'COM3'`

**解决**:
1. 关闭其他占用该端口的程序（如串口调试助手）
2. 在设备管理器中禁用/重新启用该端口
3. 以管理员身份运行 Python
4. 检查驱动是否正确安装

### Q3: DLL 加载失败
**错误**: `OSError: [WinError 126] 找不到指定的模块`

**解决**:
1. 确认 DLL 路径正确（使用绝对路径）
   ```yaml
   dll_path: "C:\\Zolix\\SDK\\spec.dll"  # 双反斜杠
   ```
2. 确认 DLL 与 Python 位数匹配（64-bit Python → x64 DLL）
3. 安装 Visual C++ Redistributable:
   - 下载: https://aka.ms/vs/17/release/vc_redist.x64.exe
4. 使用 Dependency Walker 检查 DLL 依赖:
   - 下载: https://www.dependencywalker.com/

### Q4: NNCam 相机无法检测
**错误**: `DeviceError: no nncam camera found`

**解决**:
1. 确认相机已连接（USB）
2. 安装相机驱动（查看 `nncamsdk.20240325\driver\`）
3. 测试 SDK 示例程序（`nncamsdk.20240325\samples\`）
4. 检查 `dll_path` 是否指向正确的 DLL

### Q5: 前端无法连接后端
**错误**: `Network Error` 或 `CORS Error`

**解决**:
1. 确认后端已启动（访问 http://127.0.0.1:8008/docs）
2. 检查防火墙设置（允许端口 8008）
3. 修改前端配置（如使用不同 IP）:
   ```typescript
   // frontend/src/config.ts
   export const API_BASE_URL = 'http://127.0.0.1:8008';
   ```

### Q6: pyserial 超时
**错误**: `DeviceError: ... read timed out`

**解决**:
1. 增加超时时间（修改源码中的 `*_TIMEOUT_S` 常量）
2. 检查波特率设置（`devices.yaml` 中 `baudrate`）
3. 测试串口连接:
   ```python
   import serial
   ser = serial.Serial('COM3', 9600, timeout=1)
   print(f"Connected to {ser.name}")
   ser.close()
   ```
4. 检查串口线缆和硬件电源

### Q7: 路径找不到
**错误**: `FileNotFoundError: [Errno 2] No such file or directory`

**解决**:
1. 使用绝对路径:
   ```yaml
   dll_path: "C:\\Users\\YourName\\Documents\\project\\nncam.dll"
   ```
2. 或使用相对于项目根目录的路径（自动解析）
3. 检查路径分隔符（使用 `\\` 或 `/`）

---

## 性能优化

### 1. Windows Defender 排除
1. 打开 Windows 安全中心 → 病毒和威胁防护 → 管理设置
2. 滚动到"排除项" → 添加或删除排除项
3. 添加以下目录:
   - 项目根目录
   - `.venv` 虚拟环境
   - DLL 所在目录

### 2. COM 端口缓冲区
1. 打开设备管理器 → 端口(COM 和 LPT)
2. 右键点击 COM 端口 → 属性
3. 端口设置 → 高级
4. 增加接收缓冲区（如 4096）

### 3. 进程优先级
启动后端时设置高优先级：
```cmd
start /HIGH .venv\Scripts\python.exe -m uvicorn lab_auto.api.main:app --host 127.0.0.1 --port 8008
```

### 4. 禁用不必要的后台服务
- 关闭 OneDrive 同步
- 关闭自动更新（临时）
- 关闭浏览器后台进程

---

## 开发工具推荐

### Python 开发
- **IDE**: PyCharm / VS Code
- **调试工具**: `ipdb` (pip install ipdb)
- **串口调试**: Serial Port Monitor / RealTerm

### 前端开发
- **IDE**: VS Code (推荐扩展: ESLint, Prettier)
- **浏览器**: Chrome DevTools

### 硬件调试
- **串口工具**: 
  - SSCOM (串口调试助手)
  - RealTerm
  - Putty
- **Modbus 工具**: 
  - Modbus Poll (读取寄存器)
  - Modbus Slave (模拟设备)

---

## 卸载

### 完全移除
```cmd
REM 停止所有服务
taskkill /F /IM python.exe
taskkill /F /IM node.exe

REM 删除虚拟环境
rmdir /S /Q .venv

REM 删除 Node 模块
rmdir /S /Q frontend\node_modules

REM 删除数据文件（可选）
rmdir /S /Q data
```

---

## 技术支持

### 日志位置
- **后端日志**: 控制台输出（可重定向到文件）
  ```cmd
  start_api.bat > logs\api.log 2>&1
  ```
- **前端日志**: 浏览器控制台（F12）
- **设备状态**: `data/stage_state.json`

### 联系方式
- 项目文档: `docs/`
- 配置示例: `config/*.yaml.example`
- 问题反馈: [项目 Issue 页面]

---

## 附录

### A. 启动脚本说明

#### start_api.bat
```batch
@echo off
cd /d "%~dp0"
call .venv\Scripts\activate.bat
set PYTHONPATH=src
echo Starting FastAPI server on http://127.0.0.1:8008
echo API documentation: http://127.0.0.1:8008/docs
echo Press Ctrl+C to stop
uvicorn lab_auto.api.main:app --host 127.0.0.1 --port 8008 --reload
pause
```

#### start_frontend.bat
```batch
@echo off
cd /d "%~dp0\frontend"
echo Starting Vite development server...
echo Frontend will be available at http://localhost:5173
npm run dev
pause
```

### B. 环境变量
可在 `.venv\Scripts\activate.bat` 中添加：
```batch
set PYTHONPATH=src
set LOG_LEVEL=DEBUG
set API_HOST=127.0.0.1
set API_PORT=8008
```

### C. Windows 服务化（高级）
使用 NSSM 将后端注册为 Windows 服务：
1. 下载 NSSM: https://nssm.cc/download
2. 安装服务:
   ```cmd
   nssm install RamanAPI "C:\path\to\.venv\Scripts\python.exe" "-m uvicorn lab_auto.api.main:app --host 127.0.0.1 --port 8008"
   nssm set RamanAPI AppDirectory "C:\path\to\project"
   nssm set RamanAPI AppEnvironmentExtra PYTHONPATH=src
   nssm start RamanAPI
   ```

---

**最后更新**: 2026-07-01  
**版本**: 1.0
