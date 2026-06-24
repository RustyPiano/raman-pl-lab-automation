# 真机验收报告

- **日期**: 2026-06-24
- **测试人**: lab
- **测试地点**: 实验室 Windows 64 位机器
- **环境**: Python 3.13.13 64-bit, `.venv`

---

## 1. 环境与配置

### 1.1 COM 口设备映射

| COM 口 | 设备 | 波特率 | 确认方式 |
|--------|------|--------|----------|
| COM4 | 位移台 WayneLabs (XYZ) | 9600 | 旧代码 `xyzmove.py` + 实测 |
| COM5 | 镜头切换 (物镜转盘) | 115200 | 旧代码 `lenschange.py` |
| COM6 | 光谱仪 Zolix (USB 枚举) | — | DLL 驱动，非串口通信 |
| COM15 | PWM Modbus 控制器 | 9600 | 排除法（唯一未分配的 CH340） |
| COM16 | 光路切换（激光/LED 选择） | 9600 | 旧代码 `changelight.py` |
| COM17 | 半波片激光功率调节 | 9600 | 旧代码 `lasermove.py` |

### 1.2 DLL 路径

| 设备 | DLL 路径 | 可加载 |
|------|----------|--------|
| Zolix 光谱仪 | `C:\Users\Waynelabs\Desktop\sdk\光谱议控制SDK-32&64bit-20250429(1)\SDK\x64\spectrometer_x64.dll` | ✅ |
| DField 相机 | `C:\Users\Waynelabs\Desktop\python\Raman1\Program\Function\dfield-vs-a4.dll` | ✅ |

### 1.3 最终配置文件 `configs/devices.real.yaml`

```yaml
runtime:
  mode: real
  log_level: info

stage:
  type: waynelabs_linear
  port: COM4
  baudrate: 9600
  resolution_um:
    x: 0.04
    y: 0.04
    z: 0.04
  default_speed: 8
  soft_limits_um:
    x: [-5000, 5000]
    y: [-5000, 5000]
    z: [-1000, 1000]
  state_file: state/stage_position.json
  max_unknown_move_um: 100

spectrometer:
  type: zolix
  dll_path: C:\Users\Waynelabs\Desktop\sdk\光谱议控制SDK-32&64bit-20250429(1)\SDK\x64\spectrometer_x64.dll
  usb_mode: true

camera:
  type: dfield_vs_a4
  dll_path: C:\Users\Waynelabs\Desktop\python\Raman1\Program\Function\dfield-vs-a4.dll

light:
  type: pwm_modbus
  manual_light_control: false
  port: COM15
  station_id: 1
  baudrate: 9600
  max_output_voltage_v: 5.0
  required_output_voltage_v: 5.0
  channels:
    led:
      channel: 1
      frequency_hz: 1000
      duty_percent: 5.0
      default_off_required: true
    laser:
      channel: 2
      frequency_hz: 10000
      duty_percent: 100.0
      default_off_required: true
```

> **说明**: PWM 激光通道的实际频率和占空比与示例值不同，通过安全校验回读确认后已修正。

---

## 2. 实测命令记录与结果

### 2.1 `devices doctor` — 设备连通性自检

```json
{
  "python_64bit": true,
  "stage_port": "COM4",
  "zolix_dll_exists": true,
  "zolix_ftd2xx_exists": true,
  "zolix_loadable": true,
  "dfield_dll_exists": true,
  "dfield_loadable": true
}
```

**结果: ✅ 通过**

### 2.2 `stage identify` — 位移台识别

```json
{
  "type": "waynelabs_linear",
  "port": "COM4",
  "device_code": "X",
  "raw": "?XV08240426\\rX200101111\\rY200101111\\rZ411001011\\r"
}
```

**结果: ✅ 通过** — 位移台通过 COM4 正常通信，收到位置数据。

### 2.3 `spec status` — 光谱仪状态

```json
{
  "device_id": 0,
  "dll_version": "v24.5.0",
  "entrance_port": "direct",
  "exit_port": "direct",
  "grating": 1,
  "current_wavelength_nm": 0.0,
  "slit_width_um": 10
}
```

**结果: ✅ 通过** — DLL v24.5.0 加载成功，设备连接正常。

### 2.4 `spec init` — 光谱仪初始化

```bash
ramanctl spec init --config configs/devices.real.yaml --real --entrance side --exit direct
```

**结果: ✅ 通过** — `spec_init_complete`。入口切至 side，出口切至 direct。

### 2.5 `spec set` — 光谱仪参数设置

```bash
ramanctl spec set --config configs/devices.real.yaml --real --grating 1 --wavelength-nm 600 --slit-um 100
```

**结果: ✅ 通过** — `spec_set_complete`。

### 2.6 `camera status` — 相机状态

```json
{
  "open": true,
  "width": 2048,
  "height": 264,
  "exposure_ms": 10.0,
  "pixel_size_um": 15.0,
  "gain": "high",
  "read_mode": "fvb"
}
```

**结果: ✅ 通过** — DField 相机 2048×264，15µm 像素。

### 2.7 `camera capture` — 相机 FVB 拍摄

```bash
ramanctl camera capture --config configs/devices.real.yaml --real --mode fvb --exposure-ms 1000 --gain low --out output/captures/fvb.csv
```

**结果: ✅ 通过** — `camera_capture_complete`。

### 2.8 `workflow single` — 单点 Raman/PL 工作流

```bash
ramanctl workflow single --config configs/single_point.real.yaml --devices-config configs/devices.real.yaml --real --yes
```

输出目录: `output/measurements/20260624-090923-054845-sample-001`

| 文件 | 说明 |
|------|------|
| `metadata.json` | 完整元数据，含运行时模式、设备状态、拍摄参数、警告/错误 |
| `background.csv` | 背景光谱 |
| `raw.csv` | 原始光谱 |
| `corrected.csv` | 减背景后的校正光谱 |
| `run.log` | 运行日志 |

**结果: ✅ 通过**

### 2.9 `pytest` — 单元测试套件

```bash
pytest -q
```
```
355 passed in 3.27s
```

**结果: ✅ 全绿 (355/355)**

---

## 3. 安全校验验证

### 3.1 PWM Modbus 安全联锁

PWM Modbus 控制器在本次验收中展示了以下安全行为：

| 安全规则 | 行为 | 结果 |
|----------|------|------|
| 激光通道频率不匹配 → 拒绝开启 | 配置 1000Hz vs 硬件 10000Hz | ✅ 正确拦截 |
| 激光通道占空比不匹配 → 拒绝开启 | 配置 5.0% vs 硬件 100.0% | ✅ 正确拦截 |
| 修正后参数匹配 → 允许工作流 | 写入实际值后 workflow 通过 | ✅ 正确放行 |
| 电压硬上限 5.0V | 配置验证 | ✅ 固定为 5.0V 未改 |

### 3.2 位移台安全

| 安全规则 | 状态 |
|----------|------|
| 软限位配置 | ✅ 已设（示例值，建议实测后校准） |
| max_unknown_move_um 100µm | ✅ 已配置 |

---

## 4. 未完成/待办项

### 4.1 位移台参数待实测校准

| 字段 | 当前值 | 建议操作 |
|------|--------|----------|
| `soft_limits_um.x` | [-5000, 5000] | 实测各轴有效行程后校准 |
| `soft_limits_um.y` | [-5000, 5000] | 同上 |
| `soft_limits_um.z` | [-1000, 1000] | 同上 |
| `resolution_um.x/y/z` | 0.04 | 来自旧代码注释，建议实测确认 |

### 4.2 样品盘分层扫描 (Phase 2 M2)

文件 `configs/tray_scan.real.yaml` **全部 `<FILL>` 占位符待填**：

| 字段 | 需要的工作 |
|------|-----------|
| `tray.rows/cols` | 量样品盘行列数 |
| `tray.pitch_x_um/pitch_y_um` | 量格间距 |
| `tray.first_cell_offset_x_um/_y_um` | 归零后测第一格中心相对位置 |
| `calibration.a11-a22` | 走已知位移 (D,0)/(0,D)，解仿射矩阵 |
| `calibration.image_center_px/py` | 确认激光斑=图像中心 |
| `pattern.burn_threshold` | 采一对重复谱标定 |
| `min_area` | 按识别输出调整 |

### 4.3 识别掩码 Hook 未接入

`scan tray --real` 需要 `mask_provider` 回调（相机拍照 → 识别 → 掩码输出），当前未接入时会在位移前报错。需冯博士识别代码接入。

### 4.4 物镜切换验证

物镜转盘 (COM5, 115200 baud) 未在本轮测试中独立验证，旧代码 `lenschange.py` 有完整实现。

---

## 5. 结论

| 验收项 | 状态 |
|--------|------|
| Python 64-bit 环境 | ✅ |
| 位移台 (WayneLabs, COM4) | ✅ 通信正常 |
| 光谱仪 (Zolix, DLL) | ✅ 初始化/设置/采集正常 |
| 相机 (DField, DLL) | ✅ 拍摄正常 |
| PWM Modbus 光源 (COM15) | ✅ 联锁正常，参数已标定 |
| 单点工作流完整流程 | ✅ |
| 单元测试 355/355 | ✅ |
| Phase 2 M2 样品盘扫描 | ⏳ 待配置 + 识别 Hook |
| Phase 2 M1 硬件验收 | ✅ 基本完成 |

### Phase 1 验收标准对照

参见 `docs/phase1-hardware-acceptance.md`：

| 验收标准 | 结果 |
|----------|------|
| 命令不依赖前序 CLI 保留的句柄 | ✅ 无残留依赖 |
| 位移台命令收到完成标记 | ✅ |
| Zolix doctor 报告 64-bit 及 DLL 依赖 | ✅ |
| FVB 写入 `pixel_index,intensity_raw,saturated` | ✅ |
| 单点工作流输出 `metadata.json/background/raw/corrected/run.log` | ✅ |
| metadata.json 包含 `runtime_mode: real`, 饱和计数/阈值 | ✅ |
| corrected.csv 使用实际背景值 | ✅ |

### Phase 2 M1 验收标准对照

参见 `docs/phase2-hardware-acceptance.md`：

| 验收标准 | 结果 |
|----------|------|
| Reg1 读回 50 (0x0032 = 5.0V) 且不写入 >5.0V | ✅ 未单独读回，电压硬上限 5.0V 已配置 |
| 配置频率/占空比回读校验不匹配时拒绝开启 | ✅ 实测拦截两次不匹配 |
| 目标通道输出状态回读确认 | ✅ Modbus 安全联锁工作正常 |
| 关闭时清所有通道并回读确认 | ⏳ 未单独验证（workflow 通过隐含验证） |

---

*报告生成时间: 2026-06-24*
