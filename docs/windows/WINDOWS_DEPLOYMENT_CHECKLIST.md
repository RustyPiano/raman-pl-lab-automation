# Windows 部署验证清单

## 部署前检查

### 硬件准备
- [ ] Zolix 光谱仪 USB 线已连接
- [ ] WayneLabs 载物台串口线已插入
- [ ] PWM 光源控制器已通电并连接串口
- [ ] NNCam 相机 USB 已连接
- [ ] 所有设备驱动已安装
- [ ] 设备管理器中无黄色感叹号

### 软件准备
- [ ] Windows 10/11 (64-bit)
- [ ] Python 3.12+ 已安装
- [ ] Node.js 18+ 已安装
- [ ] Git for Windows 已安装
- [ ] Visual C++ Redistributable 已安装（如需要）

### DLL/SDK 准备
- [ ] Zolix 光谱仪 DLL 已就位
- [ ] NNCam SDK DLL 已就位 (`nncamsdk.20240325/win/x64/nncam.dll`)
- [ ] 所有 DLL 位数与 Python 匹配（64-bit 推荐）

---

## 安装验证

### 步骤 1: 运行自动安装脚本
```cmd
install_windows.bat
```
**预期结果**:
- [ ] Python 版本显示正常
- [ ] Node.js 版本显示正常
- [ ] 虚拟环境创建成功
- [ ] Python 依赖安装成功（无错误）
- [ ] 前端依赖安装成功（无错误）

### 步骤 2: 检测 COM 端口
```cmd
check_ports.bat
```
**预期结果**:
- [ ] 显示可用 COM 端口列表
- [ ] 识别到载物台串口（如 COM5）
- [ ] 识别到 PWM 控制器串口（如 COM17）

**记录 COM 端口**:
- 载物台: COM______
- PWM 光源: COM______
- 其他: COM______

### 步骤 3: 配置设备文件
```cmd
copy devices.yaml.windows devices.yaml
notepad devices.yaml
```
**修改项**:
- [ ] `stage.port` → 实际 COM 端口
- [ ] `light.port` → 实际 COM 端口
- [ ] `spectrometer.dll_path` → Zolix DLL 绝对路径
- [ ] `camera.dll_path` → NNCam DLL 路径（确认正确）
- [ ] `light.channels.laser.channel` → 硬件通道号
- [ ] `light.channels.led.channel` → 硬件通道号

### 步骤 4: 启动后端服务
```cmd
start_api.bat
```
**预期结果**:
- [ ] 虚拟环境激活成功
- [ ] Uvicorn 启动成功
- [ ] 显示 "Application startup complete"
- [ ] 无 DLL 加载错误
- [ ] 无 COM 端口访问错误

**访问测试**:
- [ ] http://127.0.0.1:8008 返回 JSON
- [ ] http://127.0.0.1:8008/docs 显示 API 文档

### 步骤 5: 启动前端界面
```cmd
start_frontend.bat
```
**预期结果**:
- [ ] npm 依赖加载成功
- [ ] Vite 开发服务器启动
- [ ] 显示 "Local: http://localhost:5173"
- [ ] 无编译错误

**访问测试**:
- [ ] http://localhost:5173 显示界面
- [ ] 控制台无错误（F12）
- [ ] 可以连接到后端 API

---

## 功能验证

### API 端点测试
访问 http://127.0.0.1:8008/docs 测试以下端点:

#### 系统状态
- [ ] GET `/api/status` 返回系统信息
- [ ] 响应包含设备状态

#### 载物台控制
- [ ] POST `/api/stage/home` 回零成功（小心执行）
- [ ] POST `/api/stage/move` 移动测试（小距离）
- [ ] GET `/api/stage/position` 读取位置

#### 光谱仪控制
- [ ] GET `/api/spectrometer/status` 读取状态
- [ ] POST `/api/spectrometer/set_wavelength` 设置波长
- [ ] POST `/api/spectrometer/set_slit` 设置狭缝

#### 相机控制
- [ ] GET `/api/camera/status` 检测相机
- [ ] POST `/api/camera/capture` 拍摄测试图像
- [ ] 验证图像保存路径

#### 光源控制
- [ ] GET `/api/light/status` 读取状态
- [ ] POST `/api/light/laser_off` 关闭激光（安全测试）
- [ ] POST `/api/light/led_on` 打开 LED（可选）

---

## 硬件集成测试

### 载物台测试
```cmd
.venv\Scripts\activate.bat
ramanctl stage status
ramanctl stage move --axis x --distance 100  # 移动 100μm
ramanctl stage move --axis x --distance -100  # 返回
```
**验证**:
- [ ] 命令无错误
- [ ] 载物台实际移动
- [ ] 位置记录正确

### 光谱仪测试
```cmd
ramanctl spectrometer status
ramanctl spectrometer set-wavelength 532.0
```
**验证**:
- [ ] DLL 加载成功
- [ ] 波长设置成功
- [ ] 读取当前波长正确

### 相机测试
```cmd
ramanctl camera capture --output test.jpg
```
**验证**:
- [ ] 相机检测成功
- [ ] 图像保存成功
- [ ] 图像质量正常

### 光源测试（谨慎）
```cmd
ramanctl light status
ramanctl light laser-off  # 确保激光关闭
```
**验证**:
- [ ] Modbus 通信成功
- [ ] 读取通道状态正确
- [ ] 控制指令生效

---

## 性能验证

### 响应时间测试
- [ ] API 响应 < 100ms（简单查询）
- [ ] 载物台移动响应 < 500ms
- [ ] 相机拍摄 < 2s
- [ ] 光谱采集 < 5s

### 稳定性测试
- [ ] 连续移动 10 次无错误
- [ ] 连续拍摄 10 张无错误
- [ ] 长时间运行（1 小时）无崩溃

### 资源使用
- [ ] Python 进程 < 500MB 内存
- [ ] CPU 使用 < 30%（空闲时）
- [ ] 无内存泄漏（长时间运行）

---

## 常见问题检查

### Python 环境
```cmd
.venv\Scripts\activate.bat
python --version
pip list | findstr "serial yaml fastapi"
```
**预期**:
- [ ] Python 3.12+
- [ ] pyserial, PyYAML, fastapi 已安装

### COM 端口
```cmd
python -m serial.tools.list_ports
```
**预期**:
- [ ] 列出所有 COM 端口
- [ ] 目标设备端口可见

### DLL 依赖
```cmd
where python
dir /s nncam.dll
```
**预期**:
- [ ] Python 路径正确
- [ ] DLL 文件存在

---

## 回滚方案

### 停止所有服务
```cmd
taskkill /F /IM python.exe
taskkill /F /IM node.exe
```

### 删除虚拟环境
```cmd
rmdir /S /Q .venv
```

### 重新安装
```cmd
install_windows.bat
```

---

## 部署签收

### 基础功能
- [ ] 后端 API 启动正常
- [ ] 前端界面访问正常
- [ ] 所有硬件设备识别
- [ ] 基本控制命令响应

### 硬件集成
- [ ] 载物台移动正常
- [ ] 光谱仪波长设置正常
- [ ] 相机拍摄正常
- [ ] 光源控制正常（如已配置）

### 文档完整性
- [ ] WINDOWS_SETUP.md 阅读完成
- [ ] WINDOWS_COMPATIBILITY_REPORT.md 已审查
- [ ] WINDOWS_QUICK_REFERENCE.md 已保存
- [ ] devices.yaml 配置正确

### 安全检查
- [ ] 激光默认关闭
- [ ] 软限位配置正确
- [ ] 紧急停止程序已知晓
- [ ] 备份配置文件已创建

---

## 签名确认

**部署人员**: _________________  
**日期**: _________________  
**Windows 版本**: _________________  
**Python 版本**: _________________  
**Node.js 版本**: _________________  

**备注**:
_______________________________________________
_______________________________________________
_______________________________________________

---

## 技术支持

遇到问题请参考:
1. **WINDOWS_SETUP.md** - 详细安装指南
2. **WINDOWS_QUICK_REFERENCE.md** - 快速参考
3. **WINDOWS_COMPATIBILITY_REPORT.md** - 兼容性分析
4. **项目文档** - `docs/project-overview.html`

**生成日期**: 2026-07-01
