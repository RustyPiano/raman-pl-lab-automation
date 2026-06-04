# 实验室 Raman/PL 自动化平台规格文档

日期：2026-06-04

## 1. 背景

实验室准备将现有卓立汉光 Raman/PL 光谱测量流程自动化，当前目标是先打通关键硬件瓶颈，形成稳定、可脚本调用、可由后续 AI Agent 编排的基础能力。

目前已有的本地资料包括：

- `自动化主要流程.docx`：老师整理的 MAPS/WayneLabs 软件人工操作流程。
- `Waynelabs SDK Instructions.pdf`：WayneLabs 电动位移台和电动光路组件的串口通信说明。
- `光谱议控制SDK-32&64bit-20250429/`：Zolix 光谱仪/单色仪 SDK、驱动、C++/LabVIEW/Python Demo。
- `DField-VS-A4-SDK-20250619/`：DField-VS-A4 CCD/相机探测器 SDK 和 C++ Demo。

现有人工流程依赖 MAPS - WayneLabs 软件。后续平台不应只模拟鼠标点击，而应优先封装底层硬件控制能力，然后提供统一 CLI 和 Python API，供脚本、上层 GUI、实验流程引擎或 AI Agent 调用。

## 2. 目标

第一阶段目标：

1. 封装 Zolix 光谱仪控制能力。
2. 封装 WayneLabs 位移台控制能力。
3. 封装 DField-VS-A4 CCD/相机采集能力。
4. 设计统一的 Raman/PL 单点测量工作流接口。
5. 提供 CLI，方便在目标 Windows 实验电脑上快速验证硬件连接和基础动作。
6. 提供 dry-run/simulated 模式，方便在无硬件或非 Windows 环境中开发、测试和给 AI Agent 预演流程。

长期目标：

1. 接入样品识别与定位算法。
2. 接入激光、LED、PWM 或其他光源控制器。
3. 支持全自动单点测量、区域 Mapping、批量任务和异常恢复。
4. 为 AI Agent 提供安全、可观测、可撤销的实验操作接口。

## 3. 非目标

第一阶段不直接实现以下内容：

- 不重写完整 MAPS 软件。
- 不做复杂 GUI。
- 不承诺无人工参与的端到端实验闭环。
- 不实现样品识别算法本身；只预留接口。
- 不实现 Mapping 扫描和 Agent tool schema；这些进入第二阶段。
- 不在 macOS 上真实控制 Zolix/DField DLL；真实联调以 Windows 64-bit 实验电脑为准。

## 4. 人工流程到自动化能力的映射

老师文档中的人工流程可拆成以下自动化能力。

### 4.1 启动与初始化

人工操作：

- 点击桌面 `MAPS - WayneLabs`。
- 进入 `Sample Stage Mapping`。
- 选择 DAQ 设备为 `Zolix`。
- 点击 Zolix 光谱仪，连接并等待初始化完成。

自动化能力：

- `devices scan`：扫描串口设备、Zolix 设备、可用相机。
- `spec status` / `spec init`：在单次命令内连接 Zolix 光谱仪、执行动作并关闭。
- `stage identify` / `stage move`：在单次命令内连接 WayneLabs 位移台、执行动作并关闭。
- `camera status` / `camera capture`：在单次命令内连接 DField 相机、执行动作并关闭。
- `system status`：汇总所有设备状态。

### 4.2 光谱仪光路配置

人工操作：

- `INPUT FLIPPER = SIDE PORT`。
- `OUTPUT FLIPPER = DIRECT PORT`。
- 点击 `Set Port to`。
- 选择 `Slit = INPUT SIDE`，设置狭缝宽度。

自动化能力：

- 设置入口端口：侧入或直入。
- 设置出口端口：直出或侧出。
- 设置狭缝宽度。
- 读取并校验当前端口、狭缝、波长、光栅状态。

对应 Zolix SDK 函数包括：

- `spec_set_entrance_port`
- `spec_get_entrance_port`
- `spec_set_exit_port`
- `spec_get_exit_port`
- `spec_set_slit_width`
- `spec_get_slit_width`
- `spec_set_slit_bandpass`
- `spec_get_slit_bandpass`

### 4.3 模式切换与光源控制

人工操作：

- `Image - LED`：白光观察模式。
- `PL/Raman`：切换到光谱采集模式。
- `Laser on` / `Laser off`：打开或关闭激光。

自动化能力：

- 定义统一 `LightController` 接口：
  - `laser_on()`
  - `laser_off()`
  - `led_on()`
  - `led_off()`
  - `set_power(percent_or_raw)`
  - `get_state()`

当前资料只说明 WayneLabs 有多路 PWM 信号发生器，可用于 LED 光源、激光光源开关和同步触发，但尚未提供该控制器的具体协议。因此第一阶段将光源控制作为可插拔接口，提供 simulated 实现和明确错误提示，待拿到协议或在目标电脑上识别实际控制方式后补真实实现。

### 4.4 样品识别与定位

人工流程中明确标注：“样品识别与定位【这部分需要和冯博士沟通算法】”。

自动化能力：

- 从相机获取图像。
- 维护相机视野中心、十字准星、像素坐标和位移台物理坐标之间的标定关系。
- 提供样品识别接口：
  - 输入：相机帧、算法配置、当前标定。
  - 输出：候选目标点、置信度、建议移动量。
- 调用位移台移动到目标点。

第一阶段只定义接口和数据结构，不实现识别算法。

### 4.5 光谱采集与后处理

人工操作：

- 选择积分时间。
- `Laser off` 后点击 `Acq` 采集背景。
- `Save BG` 保存背景。
- `Sub BG` 扣除背景。
- `Laser on` 后点击 `Acq` 采集 Raman/PL 信号。
- `Save` 保存当前光谱。

自动化能力：

- 配置采集参数。
- 采集背景谱。
- 采集样品谱。
- 执行背景扣除。
- 保存原始谱、背景谱、扣背景谱和元数据。
- 支持单次采集、连续采集和停止。

## 5. 系统架构

推荐结构为 Python 包加 CLI：

```text
lab_automation/
  pyproject.toml
  README.md
  configs/
    single_point.example.yaml
    devices.example.yaml
  src/lab_auto/
    __init__.py
    cli.py
    config.py
    errors.py
    logging.py
    devices/
      base.py
      waynelabs_stage.py
      zolix_spectrometer.py
      dfield_camera.py
      light.py
      simulated.py
    workflow/
      raman.py
      data.py
    processing/
      background.py
      calibration.py
  tests/
    test_waynelabs_protocol.py
    test_workflow_dry_run.py
```

Phase 2 可以再加入以下占位模块，但 Phase 1 骨架不要求创建：

- `src/lab_auto/workflow/mapping.py`
- `src/lab_auto/agent/tool_schema.py`

设计原则：

- 底层设备封装只负责硬件通信，不包含实验策略。
- 工作流层负责把多个硬件动作编排成实验步骤。
- CLI 调用工作流和设备接口，不直接操作 DLL 或串口。
- 所有危险动作需要显式参数或配置，例如开启激光、长距离移动、归零。
- 所有流程默认可 dry-run，输出将执行的动作和参数。

### 5.1 CLI 状态模型

Phase 1 不实现 daemon、后台服务、交互式 shell 或跨进程 session。普通 CLI 每次调用都是独立进程，因此不能假设 DLL handle、串口连接或设备状态会跨命令保留。

Phase 1 采用以下规则：

- 单设备 CLI 命令默认是 stateless：读取配置，打开设备，执行动作，读取结果，关闭设备。
- `workflow single` 是一个长生命周期命令：在同一个进程内打开所有需要的设备，按顺序执行完整单点测量流程，最后统一关闭设备。
- `open`、`close` 不作为持久 session 命令暴露给用户；需要验证连接时使用 `status`、`doctor` 或具体动作命令。
- 所有命令都必须能在 `--dry-run` 下运行，输出会执行的动作序列，不打开真实设备。
- Phase 2 可以增加 `ramanctl shell` 或 `ramanctl daemon`，用于人工调试和 AI Agent 长会话控制；Phase 1 不依赖该能力。

这条规则是实现约束。后续开发不得写出依赖跨命令连接状态的 CLI 行为。

### 5.2 Runtime mode

Phase 1 明确定义三种运行模式：

- `dry_run`：只解析配置、校验参数、打印将执行的动作序列，不打开串口、不加载 DLL、不生成真实采集数据。用于预演危险动作。
- `simulated`：使用假设备执行完整流程，可以生成确定性的假光谱和假元数据。用于无硬件环境的端到端测试。
- `real`：打开真实串口和 DLL，执行真实硬件动作。必须显式指定。

运行模式优先级：

1. CLI 参数最高：`--real`、`--dry-run`、`--simulated` 互斥，并覆盖配置文件中的 `runtime.mode`。
2. 其次读取设备配置文件中的 `runtime.mode`。
3. 如果没有任何指定，默认视为 `dry_run`。

示例 `devices.yaml` 默认使用 `dry_run`，避免误触硬件。真实上机验收应使用 `configs/devices.real.yaml`，或在命令中显式传入 `--real`。

## 6. 设备接口设计

### 6.1 WayneLabs 位移台

通信方式：

- USB 转串口，CH340 驱动。
- 串口参数：`9600 bps, 8 data bits, 1 stop bit, no parity`。
- 设备查询命令：`?S000000`。
- 多轴直线步进电机控制器识别码：`X`。

设备信息响应示例：

```text
?XV09240426\r
X200101111\r
Y200101111\r
Z411001011\r
```

运动命令格式：

```text
?<mode><speed><steps><direction>
```

示例：

```text
?X00924b
```

字段含义：

- `mode`：`X` 表示直线电机模式，`R` 表示旋转电机模式。
- `speed`：`0` 到 `9`，数值越小越快。
- `steps`：四位步数，`0001` 到 `9999` 为相对移动，`0000` 为归零。
- `direction`：
  - X 轴：`b` 靠近电机方向，`c` 远离电机方向。
  - Y 轴：`d` 靠近电机方向，`e` 远离电机方向。
  - Z 轴：`f` 靠近电机方向，`g` 远离电机方向。

运动完成返回：

- 正常完成：返回 `?` 加方向字符，例如 `?b`。
- 到达限位：返回 `?t`。
- 归零完成：返回 `?t`。

位移台 API：

```python
stage = WaynelabsStage.open(port="COM5", resolution_um={"x": 0.04, "y": 0.04, "z": 0.04})
stage.identify()
stage.move_relative(axis="x", um=100, speed=8)
stage.home(axis="x", direction="negative", speed=8)
stage.trigger(mode="open_loop")
stage.close()
```

注意事项：

- PDF 中多轴直线控制器的示例分辨率为 `1 mm / 25000 = 40 nm = 0.04 um`，但实际平台的丝杆导程和减速比必须配置化。
- 单条命令步数上限为 `9999`，长距离移动需要自动拆分成多条命令。
- 软件需要维护“相对坐标账本”，因为协议没有提供绝对位置读取接口。
- 归零会持续运动直到限位，是危险动作，CLI 必须要求显式确认或 `--yes`。

### 6.2 Zolix 光谱仪

通信方式：

- Windows DLL：`spectrometer_x64.dll` 或 `spectrometer_x86.dll`。
- 推荐优先支持 64-bit Python 和 `SDK/x64/spectrometer_x64.dll`。
- 底层可用 `ctypes` 封装。

核心 API：

```python
spec = ZolixSpectrometer.open(
    serial=None,
    dll_path="C:/RamanSDK/SDK/x64/spectrometer_x64.dll",
)
spec.initialize()
spec.set_entrance_port("side")
spec.set_exit_port("direct")
spec.set_grating(1)
spec.move_to_wavelength_nm(600.0)
spec.set_slit_width_um(index=0, width_um=100)
spec.get_status()
spec.close()
```

必须封装的 SDK 函数：

- 设备管理：`spec_get_dll_ver`、`spec_set_usb_mode`、`spec_enum_dev_count`、`spec_enum_dev_sn`、`spec_open`、`spec_close`、`spec_get_is_open`、`spec_get_error`
- 光栅与波长：`spec_set_grating`、`spec_get_grating`、`spec_move_to_wave`、`spec_move_wave`、`spec_get_curr_wave`
- 光路端口：`spec_set_entrance_port`、`spec_get_entrance_port`、`spec_set_exit_port`、`spec_get_exit_port`
- 狭缝：`spec_set_slit_width`、`spec_get_slit_width`、`spec_set_slit_bandpass`、`spec_get_slit_bandpass`
- 可选：滤光片、快门、触发、光谱拼接、像素到波长转换

注意事项：

- 厂家 Python Demo 不是权威封装；存在硬编码 DLL 路径、未实现函数和个别函数名错误。
- 应以 `SDK/inc/spectrometer.h` 和 VS Demo 为准。

端口枚举映射：

- Python API 和 YAML 使用规范化字符串，首选 `direct` 和 `side`。
- `entrance_port: direct` 调用 `spec_set_entrance_port(id, true)`；`entrance_port: side` 调用 `spec_set_entrance_port(id, false)`。
- `exit_port: direct` 调用 `spec_set_exit_port(id, true)`；`exit_port: side` 调用 `spec_set_exit_port(id, false)`。
- `front` 可作为 `direct` 的兼容别名读入，但保存到元数据时统一写 `direct`。
- `get_entrance_port` 和 `get_exit_port` 返回 `true` 时映射为 `direct`，返回 `false` 时映射为 `side`。

### 6.3 DField-VS-A4 CCD/相机

通信方式：

- Windows DLL：`dfield-vs-a4.dll`。
- 推荐优先支持 64-bit Python 和 `x64/dfield-vs-a4.dll`。

核心 API：

```python
camera = DFieldCamera.open(
    dll_path="C:/RamanSDK/DField/x64/dfield-vs-a4.dll",
)
camera.set_exposure_ms(1000)
camera.set_gain("low")
camera.set_read_mode("fvb")
camera.set_bin(x=1, y=1)
frame = camera.capture()
camera.close()
```

必须封装的 SDK 函数：

- `a4_open`
- `a4_close`
- `a4_get_exposure`
- `a4_set_exposure`
- `a4_set_gain`
- `a4_get_gain`
- `a4_get_detector_size`
- `a4_get_pixel_size`
- `a4_set_read_mode`
- `a4_get_read_mode`
- `a4_set_bin`
- `a4_get_bin`
- `a4_set_roi`
- `a4_get_roi`
- `a4_single_capture`
- `a4_set_cooling_temp`
- `a4_get_cooling_temp`
- `a4_get_current_temp`
- `a4_set_flip`
- `a4_get_flip`

注意事项：

- DField C++ Demo 调用了 `a4_set_trigger_mode(1)`，但当前头文件和 DLL 导出符号都没有该函数。实现时不得依赖该调用。
- `a4_single_capture` 返回原始 buffer；需要在封装层根据读出模式、ROI、binning 转成一维谱或二维图像。

枚举映射：

- `gain: high` 调用 `a4_set_gain(0)`；`gain: low` 调用 `a4_set_gain(1)`。
- `a4_get_gain()` 返回 `0` 时映射为 `high`，返回 `1` 时映射为 `low`。
- `read_mode: fvb` 调用 `a4_set_read_mode(0)`；`read_mode: image` 调用 `a4_set_read_mode(1)`。
- `a4_get_read_mode()` 返回 `0` 时映射为 `fvb`，返回 `1` 时映射为 `image`。
- 封装层只暴露字符串枚举；ctypes adapter 内部负责整数转换。

### 6.4 Windows DLL 运行依赖

Zolix 和 DField 都是 Windows DLL 接入。Phase 1 必须把 DLL 加载规则写进实现，而不是依赖当前工作目录偶然可用。

运行环境要求：

- Windows 64-bit。
- Python 64-bit，位数必须与 `spectrometer_x64.dll` 和 `dfield-vs-a4.dll` 一致。
- Visual C++ Redistributable 已安装。Zolix 目录中提供 `VC Redist/VC_redist_15_19.x64.exe`。
- Zolix USB 驱动已安装。Zolix SDK 目录包含 FTDI D2XX 相关驱动和 DLL。

Zolix DLL 搜索路径：

- 主 DLL：`光谱议控制SDK-32&64bit-20250429/SDK/x64/spectrometer_x64.dll`。
- 依赖 DLL：`光谱议控制SDK-32&64bit-20250429/SDK/x64/ftd2xx.dll`。
- 实现必须在加载 `spectrometer_x64.dll` 前把 `SDK/x64` 加入 DLL 搜索路径。
- Python 3.8+ 应优先使用 `os.add_dll_directory(str(sdk_x64_dir))`。
- 不得只传主 DLL 绝对路径而忽略依赖 DLL 所在目录。

DField DLL 搜索路径：

- 主 DLL：`DField-VS-A4-SDK-20250619/x64/dfield-vs-a4.dll`。
- 当前资料未显示额外依赖 DLL；实现仍应把 `x64` 目录加入 DLL 搜索路径。

`ctypes` 签名来源：

- Zolix 以 `SDK/inc/spectrometer.h` 为准。
- DField 以 `dfield-vs-a4.h` 为准。
- 厂家 Python Demo 只能作为示例，不得作为函数名、参数类型和返回值的唯一依据。

`devices doctor` 必须检查：

- Python 是否为 64-bit。
- 配置中的 DLL 文件是否存在。
- DLL 目录是否包含 Zolix 的 `ftd2xx.dll`。
- 是否能加载主 DLL。
- 是否能调用版本查询函数：
  - Zolix：`spec_get_dll_ver`
  - DField：加载 DLL 后检查必要导出符号，真实连接在上机测试中验证。

### 6.5 光源控制器

第一阶段定义接口，不绑定具体硬件：

```python
light = LightController.open(mode="manual")
light.led_on()
light.led_off()
light.laser_on()
light.laser_off()
light.set_power(10)
light.get_state()
```

真实实现待确认以下信息：

- 激光是否由 WayneLabs PWM 信号发生器控制。
- PWM 控制器是否也采用同一串口协议。
- MAPS 当前电脑中是否有额外 DLL、串口、USB HID 或网口接口。
- 激光安全联锁状态能否软件读取。

在真实接口确认前，工作流必须支持 `manual_light_control=true`，即在需要开关激光时提示人工操作并等待确认。

## 7. CLI 设计

命令名暂定为 `ramanctl`。

### 7.1 设备扫描

```bash
ramanctl devices scan --dry-run
ramanctl devices status --config configs/devices.yaml
ramanctl devices doctor --config configs/devices.yaml
```

输出内容：

- 串口列表和 WayneLabs 设备类型。
- Zolix 光谱仪数量和序列号。
- DField 相机连接状态。
- 当前 runtime mode：`dry_run`、`simulated` 或 `real`。

### 7.2 位移台

```bash
ramanctl stage identify --config configs/devices.yaml
ramanctl stage move --config configs/devices.yaml --axis x --um 100 --speed 8
ramanctl stage move --config configs/devices.yaml --axis y --um -50 --speed 8
ramanctl stage home --config configs/devices.yaml --axis x --direction negative --speed 8 --yes
ramanctl stage trigger --config configs/devices.yaml --mode open-loop
```

### 7.3 光谱仪

```bash
ramanctl spec status --config configs/devices.yaml
ramanctl spec init --config configs/devices.yaml --entrance side --exit direct
ramanctl spec set --config configs/devices.yaml --grating 1 --wavelength-nm 600 --slit-um 100
```

### 7.4 相机

```bash
ramanctl camera status --config configs/devices.yaml
ramanctl camera capture --config configs/devices.yaml --mode fvb --exposure-ms 1000 --gain low --out output/captures/sample.csv
ramanctl camera temperature --config configs/devices.yaml
```

### 7.5 Raman/PL 工作流

```bash
ramanctl workflow single --config configs/single_point.yaml --dry-run
ramanctl workflow single --config configs/single_point.yaml --devices-config configs/devices.real.yaml --real --yes
ramanctl workflow background --config configs/single_point.yaml
ramanctl workflow sample --config configs/single_point.yaml
```

Mapping 扫描命令进入 Phase 2。Phase 1 只要求单点测量相关命令可执行和可验收。

`workflow` 命令的配置规则：

- `--config` 指向工作流配置，例如样品 ID、光路参数、采集参数和输出目录。
- 工作流配置可以通过 `devices_config` 引用设备配置。
- `--devices-config` 可以覆盖工作流配置中的 `devices_config`，用于同一实验参数在 dry-run、simulated 和真实硬件间切换。
- `--real`、`--dry-run`、`--simulated` 仍按全局优先级覆盖设备配置中的 `runtime.mode`。

## 8. Python API 设计

```python
from lab_auto.workflow.raman import RamanWorkflow
from lab_auto.config import load_config

workflow_config, devices_config = load_config(
    workflow_path="configs/single_point.yaml",
    devices_override=None,
)
workflow = RamanWorkflow.from_config(workflow_config, devices_config)

workflow.initialize()
workflow.prepare_optics()
workflow.acquire_background()
result = workflow.acquire_sample()
workflow.save_result(result)
workflow.shutdown()
```

面向 AI Agent 的接口应更高层，避免让 Agent 直接发送危险底层命令：

```python
workflow.measure_single_point(
    sample_id="sample-001",
    center_wavelength_nm=600,
    exposure_ms=1000,
    grating=1,
    slit_um=100,
    subtract_background=True,
)
```

AI Agent 默认只能调用受控工作流方法；底层 `stage.home`、`laser_on`、长距离移动等危险操作需要显式权限或人工确认。

## 9. Spectrum/Frame 数据模型

Phase 1 必须明确区分相机原始帧和光谱数据，避免把 DField buffer 简单保存成无法解释的 CSV。

### 9.1 DField CaptureFrame

`DFieldCamera.capture()` 返回 `CaptureFrame`：

```python
CaptureFrame(
    read_mode="fvb",
    width=2048,
    height=1,
    bin_x=1,
    bin_y=1,
    roi=None,
    exposure_ms=1000.0,
    gain="low",
    values=[12345, 12410, 12388],
    saturated_count=0,
    metadata={},
)
```

读出模式规则：

- `FVB`：buffer 长度为 `width / bin_x`。这是 Phase 1 光谱采集 MVP 的默认模式。
- `IMAGE`：buffer 长度为 `(width / bin_x) * (height / bin_y)`。Phase 1 只将其作为诊断图像采集能力，不进入 Raman/PL 单点光谱工作流。
- `ROI + IMAGE`：`width = col_to - col_from + 1`，`height = row_to - row_from + 1`，再按 binning 计算。

饱和规则：

- 默认饱和阈值为 `65535`，来自 DField Demo 的显示逻辑。
- 保存时记录 `saturated_count` 和 `saturation_threshold`。
- 如果饱和像素数大于 0，工作流输出 warning，但 Phase 1 不自动调曝光。

平均规则：

- `frames=1` 时直接保存单帧。
- `frames>1` 时逐像素平均，保存 `raw_frames_count` 和平均后的 `intensity_raw`。
- Phase 1 不做复杂暗噪声建模；背景扣除使用独立采集的 background spectrum。

### 9.2 SpectrumData

Raman/PL 单点测量输出 `SpectrumData`：

```python
SpectrumData(
    x_axis_type="wavelength_nm",
    x=[580.123, 580.145, 580.167],
    intensity_raw=[12345, 12410, 12388],
    intensity_background=[100, 101, 99],
    intensity_corrected=[12245, 12309, 12289],
    metadata={},
)
```

X 轴规则：

- 优先使用 Zolix SDK 的 `spec_pixels_to_waves` 生成 `wavelength_nm`。
- 如果 `spec_pixels_to_waves` 缺少必要参数、调用失败或当前配置无法校准，Phase 1 仍允许输出 `pixel_index` 光谱，但必须在 `metadata.json` 中写入 `x_axis_type: pixel_index` 和 warning。
- 不允许在没有校准的情况下把 pixel index 标成 wavelength。

Phase 1 FVB 输出文件：

- `raw.csv` 保存样品采集原始谱。
- `background.csv` 保存背景谱。
- `corrected.csv` 保存背景扣除后的对齐结果。

`raw.csv` 格式：

```csv
pixel_index,wavelength_nm,intensity_raw,saturated
0,580.123,12345,false
1,580.145,12410,false
```

`background.csv` 格式：

```csv
pixel_index,wavelength_nm,intensity_background,saturated
0,580.123,100,false
1,580.145,101,false
```

`corrected.csv` 格式：

```csv
pixel_index,wavelength_nm,intensity_raw,intensity_background,intensity_corrected,saturated_raw,saturated_background
0,580.123,12345,100,12245,false,false
1,580.145,12410,101,12309,false,false
```

如果没有波长轴，各 CSV 省略 `wavelength_nm`，但必须保留 `pixel_index`。例如 `corrected.csv`：

```csv
pixel_index,intensity_raw,intensity_background,intensity_corrected,saturated_raw,saturated_background
0,12345,100,12245,false,false
1,12410,101,12309,false,false
```

单独执行 `camera capture --mode fvb --out ...` 时，没有背景和扣除结果，输出采用 `raw.csv` 的列集合。

Phase 1 IMAGE 诊断输出格式：

- 小图可保存为 CSV：`row,col,intensity_raw,saturated`。
- 大图优先保存为 NumPy `.npy` 或 TIFF；CSV 只作为调试格式。

背景扣除规则：

- `intensity_corrected = intensity_raw - intensity_background`。
- raw/background 的长度必须一致，否则工作流失败。
- raw/background 的 `x_axis_type` 必须一致，否则工作流失败。
- Phase 1 不自动做平滑、峰识别、基线拟合或强度归一化。

## 10. 配置文件

示例 `devices.yaml`：

```yaml
runtime:
  mode: dry_run
  log_level: info

stage:
  type: waynelabs_linear
  port: COM5
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
  require_position_known_for_mapping: true

spectrometer:
  type: zolix
  dll_path: C:/RamanSDK/SDK/x64/spectrometer_x64.dll
  usb_mode: true

camera:
  type: dfield_vs_a4
  dll_path: C:/RamanSDK/DField/x64/dfield-vs-a4.dll

light:
  type: manual
  manual_light_control: true
```

`devices.yaml` 是开发默认配置，不应直接作为上机配置提交真实端口和路径。真实上机建议复制为 `configs/devices.real.yaml`，将 `runtime.mode` 改为 `real`，并填写目标电脑上的 DLL 路径、串口号和实际光源控制方式。

示例 `single_point.yaml`：

```yaml
devices_config: configs/devices.yaml

sample:
  id: sample-001
  operator: lab

optics:
  entrance_port: side
  exit_port: direct
  grating: 1
  center_wavelength_nm: 600
  slit_width_um: 100

acquisition:
  exposure_ms: 1000
  gain: low
  read_mode: fvb
  frames: 1
  subtract_background: true

output:
  directory: output/measurements
  formats: [csv, json]
```

配置加载规则：

- 设备命令只读取设备配置：`--config configs/devices.yaml`。
- 工作流命令读取工作流配置：`--config configs/single_point.yaml`。
- 工作流配置中的 `devices_config` 指向默认设备配置。
- 命令行 `--devices-config configs/devices.real.yaml` 覆盖 `devices_config`。
- CLI runtime 参数覆盖所有配置文件中的 `runtime.mode`。

## 11. 数据输出

每次测量生成一个目录：

```text
output/measurements/20260604-153000-sample-001/
  metadata.json
  background.csv
  raw.csv
  corrected.csv
  preview.png
  run.log
```

`metadata.json` 至少包含：

- 时间戳。
- 样品 ID。
- 设备序列号和 DLL 版本。
- 位移台相对坐标。
- 光栅、中心波长、狭缝宽度。
- 曝光时间、增益、读出模式、binning、ROI。
- 背景扣除参数。
- 操作模式：`real`、`dry_run`、`simulated`。
- 错误和警告列表。

## 12. 安全策略

### 12.1 位移台坐标状态机

WayneLabs 串口协议没有提供绝对位置读取接口，因此软件必须维护坐标可信状态。

位移台坐标状态：

- `unknown`：刚启动、断连后重连、配置变更、状态文件缺失、人工移动后。软件不知道当前位置。
- `homed`：执行过归零，且归零方向和限位已确认。软件可从机械零点维护相对坐标。
- `user_zeroed`：用户在当前物理位置执行人工设零。软件可从用户零点维护相对坐标，但可信度低于 `homed`。

状态转换：

- 启动默认进入 `unknown`。
- `stage home --axis x --direction negative --yes` 成功后，对应轴进入 `homed`，坐标设为 0。
- `stage set-zero --axis x --yes` 成功后，对应轴进入 `user_zeroed`，坐标设为 0。
- 串口超时、设备重连、限位触发、配置分辨率改变后，对应轴回到 `unknown`。

动作规则：

- `unknown` 状态允许小步相对移动，用于人工找位置；单次距离不得超过 `max_unknown_move_um`。
- `unknown` 状态禁止 Mapping、软限位判断、自动样品定位和长距离移动。
- `homed` 或 `user_zeroed` 状态允许使用软限位。
- Mapping 扫描必须要求 X/Y 轴均为 `homed` 或 `user_zeroed`。
- Z 轴移动必须单独配置软限位，并默认比 X/Y 更保守。

状态文件：

- `state_file` 保存每个轴的状态、相对坐标、分辨率、最后更新时间和设备识别信息。
- 如果设备识别信息或分辨率与配置不一致，状态文件不得复用。

### 12.2 光源状态机

光源控制在 Phase 1 可能是 manual 模式，因此也需要显式状态。

光源状态：

- `unknown`：软件不知道激光/LED 状态。
- `manual_wait`：软件正在等待人工确认光源状态。
- `off_confirmed`：用户或真实控制器确认激光关闭。
- `on_confirmed`：用户或真实控制器确认激光打开。

动作规则：

- `manual_light_control: true` 时，工作流在 `laser_on` 和 `laser_off` 步骤必须打印明确提示，并等待用户确认。
- 采集背景前必须进入 `off_confirmed`。
- 采集样品前必须进入 `on_confirmed`。
- 工作流异常退出时必须提示用户确认激光关闭；如果后续接入真实光源控制器，则异常处理优先调用 `laser_off()`。

### 12.3 通用安全约束

必须实现的安全约束：

- 开启激光前输出明确提示；真实光源控制未接入前必须人工确认。
- 归零和长距离移动必须要求 `--yes` 或配置中的显式允许。
- 位移台维护软限位，超出范围拒绝执行。
- 串口命令必须完整发送，避免硬件超时后残留半条命令。
- 每个硬件动作设置超时，超时后进入错误状态。
- 发生错误时优先关闭激光或提示人工关闭激光，再停止采集。
- `dry_run` 是默认开发模式，真实硬件模式必须显式指定为 `real`。

## 13. 测试策略

无硬件测试：

- WayneLabs 命令编码测试：不同轴、方向、速度、距离生成正确命令。
- WayneLabs 返回解析测试：`?b`、`?c`、`?t`、超时、错误字符。
- 长距离移动拆分测试。
- Zolix 和 DField 的 ctypes 签名测试，使用 mock DLL 或 monkeypatch。
- Raman 工作流 dry-run 测试，验证动作顺序和元数据输出。

上机测试：

1. 只扫描设备，不移动、不开激光。
2. WayneLabs 单轴小步移动，例如 10 um。
3. WayneLabs 归零测试，确认方向和限位。
4. Zolix 连接、侧入直出、波长移动、狭缝设置。
5. DField 连接、曝光设置、单帧采集。
6. 人工控制激光的背景采集和样品采集。
7. 单点自动工作流。
8. Mapping 只做接口预留，不进入 Phase 1 真机验收。

## 14. 第一阶段开发里程碑

Phase 1 截止到 Milestone 5。Mapping、Agent 接口、session/daemon 和真实光源控制属于 Phase 2，不作为第一阶段交付验收条件。

### Milestone 1：工程骨架和 dry-run

- 创建 Python 包。
- 创建 CLI。
- 加载 YAML 配置。
- 所有设备提供 simulated 实现。
- `workflow single --dry-run` 可以输出完整动作序列。

验收命令：

```bash
ramanctl devices scan --dry-run
ramanctl workflow single --config configs/single_point.example.yaml --dry-run
pytest tests/test_workflow_dry_run.py
```

Pass 标准：

- 命令退出码为 0。
- dry-run 输出完整动作序列，不访问真实 DLL 或串口。
- 单元测试通过。

Fail 标准：

- dry-run 尝试打开真实设备。
- workflow 缺少初始化、背景、样品采集、保存中的任何一步。

### Milestone 2：WayneLabs 串口控制

- 串口扫描和设备识别。
- X/Y/Z 相对移动。
- 归零。
- 返回解析和超时处理。
- CLI 上机验证。

验收命令：

```bash
ramanctl stage identify --config configs/devices.real.yaml --real
ramanctl stage move --config configs/devices.real.yaml --real --axis x --um 10 --speed 8 --yes
ramanctl stage home --config configs/devices.real.yaml --real --axis x --direction negative --speed 8 --yes
pytest tests/test_waynelabs_protocol.py
```

Pass 标准：

- `identify` 能识别 WayneLabs 设备类型和串口。
- 10 um 小步移动执行完成，并收到对应方向返回字符。
- 归零收到 `?t`，状态文件将对应轴标记为 `homed`。
- 协议编码、返回解析、长距离拆分测试通过。

Fail 标准：

- 运动命令格式错误。
- 未收到完成字符仍报告成功。
- `unknown` 状态下允许长距离移动或 Mapping。

### Milestone 3：Zolix 封装

- ctypes 加载 DLL。
- 设备枚举、打开、关闭。
- 侧入直出、光栅、波长、狭缝。
- CLI 上机验证。

验收命令：

```bash
ramanctl devices doctor --config configs/devices.real.yaml --real
ramanctl spec status --config configs/devices.real.yaml --real
ramanctl spec init --config configs/devices.real.yaml --real --entrance side --exit direct
ramanctl spec set --config configs/devices.real.yaml --real --grating 1 --wavelength-nm 600 --slit-um 100
```

Pass 标准：

- `doctor` 确认 Python 为 64-bit，主 DLL 和 `ftd2xx.dll` 均可发现。
- `status` 能枚举或连接 Zolix 设备，并输出 DLL 版本或设备错误信息。
- `init` 成功设置侧入直出。
- `set` 成功设置光栅、中心波长和狭缝。

Fail 标准：

- 依赖 DLL 缺失时没有明确报错。
- DLL handle 被设计成跨 CLI 命令持久化依赖。
- ctypes 参数类型与头文件不一致导致调用不稳定。

### Milestone 4：DField 封装

- ctypes 加载 DLL。
- 曝光、增益、读出模式、binning、ROI。
- 单帧采集并保存 CSV。
- CLI 上机验证。

验收命令：

```bash
ramanctl camera status --config configs/devices.real.yaml --real
ramanctl camera capture --config configs/devices.real.yaml --real --mode fvb --exposure-ms 1000 --gain low --out output/captures/fvb.csv
ramanctl camera capture --config configs/devices.real.yaml --real --mode image --exposure-ms 100 --out output/captures/image.csv
```

Pass 标准：

- `status` 能连接相机并读取探测器尺寸、曝光、增益或温度。
- FVB 输出 CSV 符合 Phase 1 schema。
- IMAGE 输出按 `row,col,intensity_raw,saturated` 或配置格式保存。
- 饱和像素数写入元数据或 warning。

Fail 标准：

- 仍调用 `a4_set_trigger_mode`。
- FVB 和 IMAGE buffer 长度计算混用。
- 捕获失败但输出空文件并返回成功。

### Milestone 5：单点 Raman/PL 工作流

- 初始化设备。
- 配置光路。
- 背景采集。
- 样品采集。
- 背景扣除。
- 保存结果和元数据。
- 支持 manual light control。

验收命令：

```bash
ramanctl workflow single --config configs/single_point.example.yaml --dry-run
ramanctl workflow single --config configs/single_point.yaml --devices-config configs/devices.real.yaml --real --yes
```

Pass 标准：

- dry-run 输出完整顺序：设备检查、光路配置、提示激光关闭、背景采集、提示激光打开、样品采集、背景扣除、保存。
- 真实运行生成 `metadata.json`、`background.csv`、`raw.csv`、`corrected.csv`、`run.log`。
- 若 `spec_pixels_to_waves` 成功，CSV 包含 `wavelength_nm`；否则输出 `pixel_index` 并写入 warning。
- raw/background 长度不一致时工作流失败，不生成误导性 corrected 数据。
- 异常退出时提示确认激光关闭。

Fail 标准：

- 背景和样品采集顺序错误。
- `manual_light_control: true` 时没有等待人工确认。
- 输出缺少关键元数据。
- 任何真实硬件动作无法 dry-run 预演。

## 15. 第二阶段候选范围

以下功能进入 Phase 2，不阻塞 Phase 1 MVP：

- Mapping 网格扫描。
- 样品识别和定位算法接入。
- Agent tool schema 和权限系统。
- `ramanctl shell` 或 daemon/session 模式。
- 真实光源控制器接入。
- 自动曝光、峰识别、基线校正、批量任务调度。

## 16. 风险和待确认事项

1. 光源控制协议缺失：需要确认激光和 LED 的真实控制器、协议和安全联锁。
2. 位移台实际分辨率：PDF 示例不一定等于当前实验平台，需要老师或厂家确认丝杆导程、减速比和轴方向。
3. 位移台没有绝对位置读取：软件坐标依赖归零和相对运动账本，断电或手动移动后必须重新归零。
4. Windows DLL 位数：Python 位数必须与 DLL 位数一致，建议统一 64-bit。
5. DField Demo 存在不匹配函数：不能依赖 `a4_set_trigger_mode`。
6. 样品识别算法未定：需要和冯博士确定输入、输出、标定方式和失败策略。
7. MAPS 当前电脑的软件内容稍有差异：上机时需要核对实际硬件连接、串口号、DLL 路径和光源控制方式。

## 17. 后续 Agent 开发约束

后续 AI Agent 开发时应遵守：

- 不直接操作硬件协议字符串，除非在设备 adapter 内。
- 不绕过安全层调用激光、归零、长距离移动。
- 任何真实硬件动作都必须可 dry-run。
- 每个实验动作必须写日志。
- 所有实验输出必须保存元数据。
- 新增硬件优先实现 `BaseDevice` 风格接口，再接入工作流。
- 实验工作流应可中断、可恢复、可审计。

## 18. 建议的下一步

下一步应基于本规格文档写实现计划，明确文件结构、开发顺序和测试命令。实现计划通过后，再开始创建 Python 包和 CLI。
