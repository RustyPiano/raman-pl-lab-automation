# 实验电脑（Windows 64 位）上机部署与运行

本包是 Raman/PL 自动化平台的源码 + 配置模板 + 文档，用于在实验室那台
**Windows 64 位**机器上做真机实测。开发机是 macOS，故 `.venv/` 未随包提供，
需在本机重新建。

> ⚠️ 必须用 **64 位** Python：光谱仪/相机的 DLL 是 64 位的。

---

## 1. 安装 Python 环境（只做一次）

确认 Python ≥ 3.11、64 位：

```bat
python --version
python -c "import struct; print(struct.calcsize('P')*8, 'bit')"
```

在本包根目录建虚拟环境并安装：

```bat
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -e .[dev]
```

装好后 `ramanctl` 命令即可用（等价于 `python -m lab_auto`）。

冒烟自检（不接硬件，应全绿）：

```bat
pytest -q
```

---

## 2. 准备厂家 SDK / 驱动

`configs\devices.real.yaml` 里的 `spectrometer.dll_path` 和 `camera.dll_path`
要指向本机实际的 DLL：

- **Zolix 光谱仪**：x64 的 `spectrometer_x64.dll`
- **DField-VS-A4 相机**：x64 的相机 DLL

这些通常已随仪器装在实验机上（示例路径形如 `C:/RamanSDK/...`）。若没有，
把对应 SDK 拷到本机，再把真实路径填进配置。串口驱动（位移台 / PWM 板）
也需在设备管理器里能看到对应 COM 口。

---

## 3. 填写真机配置

两个模板（已在 `configs\` 下，按行内注释把 `<FILL...>` 换成实测值）：

- `configs\devices.real.yaml` —— 设备连接 + 安全（位移台 / 光谱仪 / 相机 / PWM 光源）
- `configs\tray_scan.real.yaml` —— 扫描 / 样品盘几何 / 标定

标 ⚠️ 的先填、要确认：软限位、PWM `max_output_voltage_v: 5.0`、激光/白光
通道号、`default_off_required: true`。标"现场采"的（calibration、tray 几何、
burn_threshold）按注释方法采完再填。

详细 preflight 与验收标准见 `docs\phase2-hardware-acceptance.md`
（Phase 1 见 `docs\phase1-hardware-acceptance.md`）。

---

## 4. 运行顺序（建议）

```bat
:: 1) 设备连通性自检
ramanctl devices doctor --config configs\devices.real.yaml --real

:: 2) 先 dry-run 看完整动作序列，不动硬件
ramanctl scan tray --config configs\tray_scan.real.yaml --dry-run

:: 3) 单点测量真机验收
ramanctl workflow single --config configs\single_point.real.yaml ^
    --devices-config configs\devices.real.yaml --real --yes

:: 4) 样品盘分层扫描真机验收（需先接入识别掩码 hook，见下）
ramanctl scan tray --config configs\tray_scan.real.yaml ^
    --devices-config configs\devices.real.yaml --real --yes
```

> 第 3 步要一个 `single_point.real.yaml`，可照 `configs\single_point.example.yaml`
> 复制后改 `devices_config` 指向 `devices.real.yaml`。

---

## 5. 注意事项

- **识别掩码 hook 未接**：`scan tray --real` 现在需要注入"相机拍照 → 识别 → 掩码"
  的回调（冯博士的识别输出）。未接入时会在**移动位移台之前**就明确报错，
  不会瞎跑——这是有意的安全设计。先用 `--dry-run` 验证流程，单点验收可独立先做。
- **安全**：位移台未归零只允许小幅微动；扫描要求 X/Y 已 homed/user_zeroed；
  激光开关走 PWM 联锁，电压硬上限 5.0 V。出错路径会尽力关激光并提示人工确认。
- **激光功率**由半波片另一套程序控制（师兄处），不在本包范围；本包只管开/关。
- 跑真机务必带 `--real`；只带 `--config` 而设备配置是 real 模式会被拒绝（要求显式 `--real`）。
