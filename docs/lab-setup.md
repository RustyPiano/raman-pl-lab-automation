# 实验室 Windows 电脑部署与真机配置

真实硬件只在实验室的 Windows 64 位电脑上运行。光谱仪和 CCD 的 DLL 是 64 位的，Python 也必须是 64 位。

每次在真机上操作前确认：操作员在场；物理急停和激光钥匙开关伸手可及；样品台上不放贵重样品；先用 `--dry-run` 看一遍动作序列。

## 1. 安装

需要 64 位 Python 3.11+、Node.js 20.19+（只用命令行时可以不装 Node.js）、Git for Windows（Claude Code 的 hooks 依赖其中的 bash）。

```bat
python -c "import struct; print(struct.calcsize('P')*8, 'bit')"
python -m venv .venv
.venv\Scripts\activate
pip install -e .[dev,api]
pytest -q
```

测试全部通过后，`ramanctl` 命令可用（等同 `python -m lab_auto`）。Web 控制台用 `scripts\start_api.bat`（自动使用 `.venv`）和 `scripts\start_frontend.bat`（第一次运行会自动安装前端依赖）启动，然后打开 http://localhost:5173 。

查看本机串口：`python -m serial.tools.list_ports`。

## 2. 厂家 DLL 与资料

仓库不包含厂家 SDK。2026-06-24 验收时实验室电脑上的 DLL 位置：

- Zolix 光谱仪：`C:\Users\Waynelabs\Desktop\sdk\光谱议控制SDK-32&64bit-20250429(1)\SDK\x64\spectrometer_x64.dll`（DLL 版本 v24.5.0，同目录需要 `ftd2xx.dll`）
- DField 相机：`C:\Users\Waynelabs\Desktop\python\Raman1\Program\Function\dfield-vs-a4.dll`

协议说明书（WayneLabs 串口说明、PWM 控制器 Modbus 协议）和老师的流程文档也只在本地，接手时向上一任维护者索取。

## 3. 现场已测得的参数（2026-06-24）

| 串口 | 设备 | 波特率 | 状态 |
|------|------|------|------|
| COM4 | WayneLabs 位移台（X/Y/Z） | 9600 | 已接入本项目 |
| COM15 | PWM 光源控制器，站号 1 | 9600 | 已接入本项目 |
| COM6 | Zolix 光谱仪（USB 枚举，通过 DLL 通信） | — | 已接入本项目 |
| COM5 | 物镜转盘 | 115200 | 未接入，旧代码 `lenschange.py` |
| COM16 | 光路切换（成像 LED / PL-Raman） | 9600 | 未接入，旧代码 `changelight.py` |
| COM17 | 半波片（激光功率） | 9600 | 未接入，旧代码 `lasermove.py` |

- PWM 通道：LED = 通道 1（1000 Hz / 5 %），激光 = 通道 2（**10000 Hz / 100 %**）。配置值必须与控制器读回值一致，否则程序拒绝开激光；06-24 正是靠这条检查发现了示例值不对。
- 控制器 Reg1 读回 50（5.0 V），由厂家工具设定，本软件不写。
- 相机：2048 × 264 像素，像素 15 µm。
- Zolix 光栅编号：1 = 1800 g/mm，2 = 600 g/mm，3 = 150 g/mm。
- 位移台 `resolution_um: 0.04` 和软限位 ±5000 / ±1000 µm 来自旧代码注释，**还没有实测**；各轴安全归零方向也还没有实测（见复验清单）。
- 激光功率由半波片的另一套程序调节，本项目只负责开关激光。

## 4. 填写真机配置

本机配置放在 `configs/` 下，被 Git 忽略。从模板复制：

| 复制 | 得到 | 要改的地方 |
|------|------|------|
| `devices.example.yaml` | `devices.real.yaml` | `runtime.mode: real`；串口与 DLL 路径；`light` 换成文件里注释掉的 `pwm_modbus` 段并填上节的通道参数；实测后的 `resolution_um`、`soft_limits_um`、`home_direction` |
| `single_point.example.yaml` | `single_point.real.yaml` | `devices_config: configs/devices.real.yaml`；样品 ID、操作员、光谱参数；实测的 `excitation_wavelength_nm`、`laser_power_mw`（只作记录） |
| `tray_scan.example.yaml` | `tray_scan.real.yaml` | 同上，另加托盘几何、标定（见第 6 节）、烧检阈值、`min_area` |

Web 控制台的设备诊断、关灯和急停读取 `configs/devices.yaml`（不存在时用 example）。要让 Web 用真机配置，把 `devices.real.yaml` 再复制一份为 `devices.yaml`，或设置环境变量 `LAB_AUTO_DEVICES_CONFIG`。Web 的真机单点测量需要 `pwm_modbus` 光源；`manual` 光源要在终端确认，只能用命令行。

## 5. 运行顺序

```bat
:: 1. 检查 DLL 与串口
ramanctl devices doctor --config configs\devices.real.yaml --real
ramanctl stage identify --config configs\devices.real.yaml --real
ramanctl spec status --config configs\devices.real.yaml --real
ramanctl camera status --config configs\devices.real.yaml --real

:: 2. 位移台归零（方向必须与 home_direction 一致，低速，手放在急停上）
ramanctl stage home --config configs\devices.real.yaml --real --axis x --direction negative --speed 8 --yes

:: 3. 单点测量
ramanctl workflow single --config configs\single_point.real.yaml --real --yes

:: 4. 托盘扫描：先预演，再在外部识别程序就绪后真机运行
ramanctl scan tray --config configs\tray_scan.real.yaml --dry-run
ramanctl scan tray --config configs\tray_scan.real.yaml --real --yes ^
    --recognition-dir output\recognition --session-id tray-YYYYMMDD-001
```

单点测量要求光谱仪能把像素换算成波长（`pixels_to_waves`），换算失败时测量直接失败并关激光。托盘扫描的识别协议见 [recognition-handoff.md](recognition-handoff.md)。

## 6. 托盘扫描需要现场测量的值

1. **激光斑是否在图像中心**：成像模式下用最低功率打开激光拍照，测量光斑中心与图像中心的像素偏差。标定以图像中心为原点，偏差明显时把光斑像素坐标填为 `image_center_px` / `image_center_py`。
2. **像素到位移台的标定**（每个物镜一组）：让位移台走已知距离，例如 (100, 0) µm 和 (0, 100) µm，记录图像中同一特征移动的像素数，然后计算矩阵：

   ```python
   from lab_auto.vision.calibration import fit_affine
   # 每项为 (位移台移动 µm, 观察到的像素位移)
   A = fit_affine([((100, 0), (-50, 1)), ((0, 100), (1, -50))])
   # A = [[a11, a12], [a21, a22]]，单位 µm/像素
   ```

   把 `a11..a22`、`objective`、图像中心和图像宽高 `image_width_px` / `image_height_px` 填进 `calibration`。宽高必须是相机原图尺寸，真机扫描缺这两项时会拒绝运行。
3. **托盘几何**：行数、列数、行列间距，以及归零后第一格中心相对原点的位置。
4. **烧检阈值**：在一个确认没有烧坏的点连续测两次，按 `relative_l2`（两次光谱差的 L2 范数除以第一次的 L2 范数）算出偏差，阈值取略大于该值。开启背景扣除时用扣除后的光谱比较。
5. **min_area**：按识别掩码中样品连通块的实际像素面积设置，过滤噪点。

换盘、重新归零、移动样品或改动标定后，必须用新的 session ID 和新的输出目录。
