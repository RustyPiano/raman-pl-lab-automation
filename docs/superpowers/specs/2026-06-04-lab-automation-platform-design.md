# 实验室 Raman/PL 自动化平台规格文档

日期：2026-06-04

## 1. 背景

实验室准备将现有卓立汉光 Raman/PL 光谱测量流程自动化，当前目标是先打通关键硬件瓶颈，形成稳定、可脚本调用、可由后续 AI Agent 编排的基础能力。

目前已有的本地资料包括：

- `自动化主要流程.docx`：老师整理的 MAPS/WayneLabs 软件人工操作流程。
- `Waynelabs SDK Instructions.pdf`：WayneLabs 电动位移台和电动光路组件的串口通信说明。
- `多路(5+1)路PWM信号发生器通讯协议说明.doc`：激光和白光 PWM 信号发生器的 RS485 Modbus RTU 通讯协议。
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
  - `set_intensity_percent(percent)`
  - `get_state()`

厂家已确认激光和白光都由多路 PWM 信号发生器输出控制，当前可通过 RS485 Modbus RTU 控制对应通道。自动化软件必须把该控制器作为独立光源适配器处理，Phase 1 默认仍允许 `manual_light_control=true`；Phase 2 真实后端只有在配置显式给出串口、非零站号、LED/激光通道映射和 5.0 V 安全上限后，才允许自动打开光源。

> **部分确认（2026-06-18）**：激光**开/关由 PWM 控制**（确认了 M1 做法）；激光**功率由半波片(HWP)控制**，是**另一套软件可控的独立程序**（在师兄处，接口待拿到）。MAPS `Laser Power Adjust` 面板：功率单位 **mW**、**按物镜有 Pmin/Pmax**（图示 50X 物镜 0.01–19.83 mW）、通过 HWP 角度（Step Angle / HWP Angle / Offset）调；**初始化时"功率会波动,可能损伤样品"**。因此后续可加一个**独立的 HWP 功率控制适配器**（如 `set_power_mw()`，按物镜 Pmin/Pmax 限幅），等师兄给接口；`set_intensity_percent()` 仍不映射到 PWM duty/Reg1（与 §6.5 一致）。M1 的 `laser_on/off` + 联锁不受影响。**PWM 通道号**从 MAPS 系统配置的 mode 页面获取（Image 模式 LED 开；测试模式 LED 关、激光开；共 5 通道，可逐个试），上机抄入 `channels` 配置。

安全假设：

- PWM 输出电压不得超过 5.0 V。根据协议文档，输出电压寄存器 `Reg1` 的单位为 0.1 V，因此 5.0 V 对应十进制 `50`、寄存器字 `0x0032`、线缆字节 `00 32`；不得把 `0x0050` 当作 5.0 V。
- `Reg1` 是全局共享输出电压，协议注释说明 `5+1` 路 PWM 电压和数控电源输出电压相同；它不是单个通道的独立电压。
- 协议文档列出 CH1-CH5 的频率、占空比和输出状态；`5+1` 中的 `+1` 暂按共享数控电源输出端处理，不按独立 PWM 通道使用，除非厂家后续确认接线和用途。
- 厂家正在测试通过 HTTP 端口开放 API 的新版软件。该 API 上线后可以作为 `LightController` 的 Phase 2 后端，但不得允许 Agent、配置文件或工作流透传任意 HTTP 命令，且必须保留同样的 5.0 V 上限、通道映射、状态读回和 dry-run 安全行为。

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
      raw/
        waynelabs_protocol.py
        zolix_ctypes.py
        dfield_ctypes.py
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

配置文件提交规则：

- 仓库只提交 `configs/devices.example.yaml` 和 `configs/single_point.example.yaml`。
- 本地运行前由用户复制生成 `configs/devices.yaml`、`configs/devices.real.yaml` 和 `configs/single_point.yaml`。
- `configs/devices.yaml` 用于 dry-run/simulated 开发默认值；`configs/devices.real.yaml` 用于真实实验电脑的 COM 口、DLL 路径和光源配置。
- 本地 `.yaml` 运行配置可能包含机器路径、端口号和样品信息，不应提交。

Phase 2 可以再加入以下占位模块，但 Phase 1 骨架不要求创建：

- `src/lab_auto/workflow/mapping.py`
- `src/lab_auto/agent/tool_schema.py`

设计原则：

- 底层设备封装只负责硬件通信，不包含实验策略。
- 工作流层负责把多个硬件动作编排成实验步骤。
- CLI 调用工作流和设备接口，不直接操作 DLL 或串口。
- 所有危险动作需要显式参数或配置，例如开启激光、长距离移动、归零。
- 所有流程默认可 dry-run，输出将执行的动作和参数。

SDK 边界分层：

- `raw` 层只做最低层绑定：Zolix/DField 按 C header 定义 `ctypes` 签名，WayneLabs 按 PDF 编解码串口命令。该层保留 native 函数名和协议字段，包括厂家 SDK 中的拼写错误。
- 真实光源接入时，PWM 信号发生器的 Modbus RTU 帧、寄存器地址和 CRC 只能出现在 `raw` 层；adapter、workflow、CLI 和 Agent 只能使用 `LightController` 的业务方法。raw 层解析任何 PWM 响应时必须校验 CRC、响应站号等于请求的非零站号、功能码匹配且不是 Modbus 异常响应、长度或 byte count 与请求寄存器数一致；不满足则视为读回失败，不得更新安全状态。
- `adapter` 层暴露干净的 Python API，负责 DLL 搜索路径、枚举映射、输入校验、错误包装、状态转换和日志；adapter 不手写 native 函数名、`ctypes` 签名或串口协议字符串，只调用 `raw` 层 helper。
- `workflow` 层只依赖 adapter 层，不直接导入 `ctypes`、厂家 Python demo 或手写串口命令字符串。

实现约束：

- 不复用厂家 Python demo 作为项目封装；demo 只能作为行为参考。
- raw 层的函数签名、寄存器地址和协议字段以 C header、PDF 或厂家协议文档为准。
- adapter 层必须把 native 不优雅命名隔离起来，例如 Zolix 的 `spec_set_turret_enbale` 只能出现在 raw 层，业务层使用 `set_enabled_turret` 这类干净名字。
- 硬件协议字符串和 native symbol 只能出现在 `src/lab_auto/devices/raw/*` 和对应 raw 层测试中；Agent、workflow、CLI 和 adapter 层都不得直接手写。
- 数据模型不得暴露平台相关 `ctypes` 类型；所有采集结果进入 workflow 前转成 Python 基础类型或明确 dtype 的数组。

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

本地 `configs/devices.yaml` 默认使用 `dry_run`，避免误触硬件。真实上机验收应使用 `configs/devices.real.yaml`，或在命令中显式传入 `--real`。

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

- 厂家 Python Demo 不是权威封装；存在硬编码 DLL 路径、未实现函数、签名错误和个别函数名错误。
- 应以 `SDK/inc/spectrometer.h` 和 VS Demo 为准。
- `spec_get_error` 在头文件中是 `void spec_get_error(int id, char* buff, int len)`；不得按 Python demo 中的两个参数和 `bool` 返回值实现。
- 头文件中的 native 拼写错误必须只保留在 raw 层，例如 `spec_set_turret_enbale` 和 `spec_get_enbaled_turret`；adapter 层暴露拼写正确的业务方法。

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
- DField API 没有设备 id、错误码、版本查询或多实例上下文，Phase 1 将其视为单相机全局状态 DLL。
- `a4_close()` 返回 `void`，adapter 层只能记录关闭动作和捕获异常，不能把关闭结果伪装成硬件确认。
- `a4_single_capture(long * buff, int size)` 的 `long` 是 Windows C `long` 语义；真实 DLL 调用只在 Windows 64-bit 验证。dry-run/mock 测试不得把 macOS/Linux 的 `ctypes.c_long` 宽度泄漏到数据模型。

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

Phase 1 仅定义统一接口、manual/simulated 后端和真实光源后端的安全约束；真实 PWM Modbus 或 HTTP 后端接入属于 Phase 2，需上机确认通道映射、安全联锁和验收标准后实施：

```python
light = LightController.open(mode="manual")
light.led_on()
light.led_off()
light.laser_on()
light.laser_off()
light.get_state()
```

已确认的 PWM 控制器协议：

- 通信方式：RS485 Modbus RTU。
- 串口参数：默认 9600 baud、8 data bits、no parity、1 stop bit；协议文档还支持 4800、19200、38400、57600、115200。
- 站号：协议示例使用 `0x01`；普通读写必须拒绝 `station_id=0`。改地址命令要求站号为 `0` 且总线上只能有一个从机，因此只能放在独立维护流程中执行，并要求物理确认总线上仅一台设备、所有输出已关闭。
- 支持功能码：`0x03` 读寄存器、`0x06` 写单个寄存器、`0x10` 写多个寄存器。
- 寄存器范围：`Reg0` 只读，`Reg1-Reg25` 可读写；文档示例主要使用 `Reg1-Reg24`。`Reg25` 用途未定义，项目不得写入，除非厂家另行确认。
- `Reg1`：全局共享输出电压，单位 0.1 V。真实适配器必须拒绝写入高于 5.0 V 的值，并在打开 LED/激光通道前读回确认该寄存器为十进制 `50`，即 `0x0032`。若需要写入，写入前必须先用 `0x03` 读回 `Reg17-Reg21` 并确认所有 PWM 输出状态均为 `0`；若任何通道已开启，必须先进入关闭或人工确认流程，不得直接修改 `Reg1`。确认数控电源输出端接线安全后，才允许写 `0x0032`，写后必须再次用 `0x03` 读回确认。
- `Reg2-Reg11`：CH1-CH5 频率，每个通道使用高 16 位和低 16 位组成 32-bit Hz 值。
- `Reg12-Reg16`：CH1-CH5 占空比，单位 0.1%。
- `Reg17-Reg21`：CH1-CH5 输出状态，`0` 为关闭，`1` 为打开。
- `Reg22`：当前显示通道。
- `Reg23`：按键锁，`0` 为关闭，`1` 为打开；普通光源工作流不得写入，避免削弱面板人工干预能力。
- `Reg24`：波特率枚举，`0=4800`、`1=9600`、`2=19200`、`3=38400`、`4=57600`、`5=115200`；普通光源工作流不得写入，避免光源打开后通信丢失。

真实实现仍需确认以下信息：

- 目标 Windows 电脑上的实际 COM 口、站号和接线方式。
- 白光与激光分别接在哪个 PWM 通道。
- 白光和激光需要的频率、占空比、默认关闭状态，以及 MAPS 软件是否会改写这些参数。
- 数控电源输出端是否接入负载；在确认接线安全前，真实自动模式不得写 `Reg1` 或打开任何 PWM 通道。
- 激光安全联锁状态能否软件读取。
- 厂家 HTTP API 上线后的端口、命令字符串、状态读取能力和错误返回格式。

在真实接口确认前，工作流必须支持 `manual_light_control=true`，即在需要开关激光时提示人工操作并等待确认。Phase 2 接入真实 PWM 后端时，`laser_on()` 和 `led_on()` 必须先验证：串口打开、非零站号响应、通道映射存在、`Reg1 == 0x0032`、非目标/未知通道关闭、数控电源输出端接线已确认安全、目标通道频率和占空比与配置中的 `frequency_hz` 和 `duty_percent` 匹配。写目标输出状态后必须读回对应 `Reg17-Reg21` 确认为 `1`。只有 `laser_on()` 完成这些读回后才允许设置 `laser_state=on_confirmed`；`led_on()` 只能设置独立 `led_state`，不得满足 `acquire_sample()` 的激光前置条件。`laser_off()`、`led_off()` 和异常处理必须 best-effort 关闭所有已配置光源通道，并读回对应输出状态为 `0`；失败时进入人工确认。

PWM 后端默认不支持通用 `set_intensity_percent(percent)`。如后续确认需要支持，它只能映射到经验证的单通道 `frequency_hz` 或 `duty_percent` 配置，不得把强度设置映射为修改 `Reg1` 全局输出电压。HTTP 后端也只能暴露 typed `LightController` 方法；如果不能读回电压和输出状态，不得进入 `laser_state=on_confirmed` 或 `led_state=on_confirmed`。

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

单独执行 `camera capture --mode fvb --out ...` 时，只有相机上下文，没有 Zolix 光栅、中心波长和像素到波长校准上下文。默认输出列为：

```csv
pixel_index,intensity_raw,saturated
0,12345,false
1,12410,false
```

只有在命令显式提供光谱标定上下文，且 `spec_pixels_to_waves` 或等价校准成功时，standalone capture 才允许增加 `wavelength_nm` 列。

Phase 1 IMAGE 诊断输出格式：

- 小图可保存为 CSV：`row,col,intensity_raw,saturated`。
- 大图优先保存为 NumPy `.npy` 或 TIFF；CSV 只作为调试格式。

背景扣除规则：

- `intensity_corrected = intensity_raw - intensity_background`。
- raw/background 的长度必须一致，否则工作流失败。
- raw/background 的 `x_axis_type` 必须一致，否则工作流失败。
- raw/background 的 `x` 数组必须逐点一致；`pixel_index` 轴要求整数完全一致，`wavelength_nm` 轴要求绝对误差不超过 `wavelength_tolerance_nm`，默认 `1e-6 nm`。超出容差时工作流失败。
- raw/background 的采集轴元数据必须一致，至少包括 `read_mode`、`bin_x`、`bin_y`、`roi`、`detector_width`、`detector_height`、`grating`、`center_wavelength_nm` 和 `slit_width_um`。不一致时工作流失败。
- Phase 1 不自动做平滑、峰识别、基线拟合或强度归一化。

## 10. 配置文件

提交文件 `configs/devices.example.yaml`：

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
  # Phase 2 真实 PWM 控制器接入后使用以下形态；通道和 setpoint 必须上机确认后填写。
  # type: pwm_modbus
  # manual_light_control: false
  # port: COMx
  # station_id: 1
  # baudrate: 9600
  # max_output_voltage_v: 5.0
  # required_output_voltage_v: 5.0
  # channels:
  #   led:
  #     channel: 1
  #     frequency_hz: 1000
  #     duty_percent: 5.0
  #     default_off_required: true
  #   laser:
  #     channel: 2
  #     frequency_hz: 1000
  #     duty_percent: 5.0
  #     default_off_required: true
```

使用时将 `configs/devices.example.yaml` 复制为本地 `configs/devices.yaml`。真实上机再复制为 `configs/devices.real.yaml`，将 `runtime.mode` 改为 `real`，并填写目标电脑上的 DLL 路径、串口号和实际光源控制方式。

提交文件 `configs/single_point.example.yaml`：

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
- 工作流命令读取工作流配置：`--config configs/single_point.yaml`。dry-run 验收也可以直接使用 `configs/single_point.example.yaml`。
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

光源控制在 Phase 1 可能是 manual 模式，因此也需要显式状态。以下状态机约束 Raman/PL 采集所需的激光状态；LED/白光状态必须单独记录，`led_on()` 不得让样品采集进入 `on_confirmed`。

激光状态：

- `unknown`：软件不知道激光状态。
- `manual_wait`：软件正在等待人工确认激光状态。
- `off_confirmed`：用户或真实控制器确认激光关闭。
- `on_confirmed`：用户或真实控制器确认激光打开。

LED 状态：

- `unknown`：软件不知道 LED/白光状态。
- `off_confirmed`：用户或真实控制器确认 LED/白光关闭。
- `on_confirmed`：用户或真实控制器确认 LED/白光打开。

动作规则：

- `manual_light_control: true` 时，工作流在 `laser_on` 和 `laser_off` 步骤必须打印明确提示，并等待用户确认。
- `type: pwm_modbus` 时，工作流不得允许未配置通道映射的 `laser_on()` 或 `led_on()`；真实适配器必须在打开通道前读回确认 `Reg1 == 0x0032`。如需写入 `Reg1`，写后必须再次用 `0x03` 读回确认。
- 真实 PWM 后端打开通道前必须读回 `Reg17-Reg21`，确认非目标/未知通道关闭；还必须读回目标通道频率和占空比，并与配置中的 `frequency_hz` 和 `duty_percent` 匹配。
- 采集背景前必须进入 `laser_state=off_confirmed`。
- 采集样品前必须进入 `laser_state=on_confirmed`。
- `led_on()` 只能设置 `led_state=on_confirmed`，不得改变 `laser_state`，也不得满足样品采集的激光前置条件。
- 工作流异常退出时必须提示用户确认激光关闭；如果后续接入真实光源控制器，则异常处理优先关闭所有已配置光源通道，并读回确认对应输出状态为 `0`，失败时进入人工确认。

### 12.3 通用安全约束

Phase 1 必须实现的安全约束：

- 开启激光前输出明确提示；真实光源控制未启用或未完成上机确认前必须人工确认。
- 归零和长距离移动必须要求 `--yes` 或配置中的显式允许。
- 位移台维护软限位，超出范围拒绝执行。
- 串口命令必须完整发送，避免硬件超时后残留半条命令。
- 每个硬件动作设置超时，超时后进入错误状态。
- 发生错误时优先关闭激光或提示人工关闭激光，再停止采集。
- `dry_run` 是默认开发模式，真实硬件模式必须显式指定为 `real`。

Phase 2 接入真实 PWM Modbus 或 HTTP 光源后端时必须额外实现的安全约束：

- PWM 光源控制器的输出电压硬上限为 5.0 V；任何配置、命令、HTTP 后端请求参数、请求体或等价命令若会设置更高电压，必须在软件层拒绝。
- `Reg1` 的 5.0 V 安全值必须按十进制 `50`、寄存器字 `0x0032`、线缆字节 `00 32` 处理；不得使用 `0x0050` 表示 5.0 V。
- 普通光源工作流禁止写 `Reg23`、`Reg24`、`Reg25` 和改地址命令；普通读写必须拒绝 `station_id=0`。
- 任何写 `Reg1` 操作前必须先用 `0x03` 读回 `Reg17-Reg21`，确认所有 PWM 输出状态均为 `0`；若任一通道已开启，必须先关闭并读回确认，或进入人工确认，不得直接修改 `Reg1`。
- PWM Modbus 写操作必须用 `0x03` 读回校验；仅依赖 `0x06` 或 `0x10` 返回帧不算状态确认。
- PWM Modbus 读回必须来自完整有效响应：CRC 正确、响应站号等于请求的非零站号、功能码匹配且不是异常响应、长度或 byte count 与请求寄存器数一致。
- 打开任一光源通道前必须读回全局输出电压、所有通道输出状态、目标通道频率和目标通道占空比；无法确认配置中的 `frequency_hz` 和 `duty_percent` 时不得进入对应状态。
- HTTP 后端只能暴露 typed `LightController` 方法，不允许 Agent、配置文件或工作流透传任意 URL、请求体或厂家命令字符串；HTTP 后端不能读回电压和输出状态时，不得进入 `laser_state=on_confirmed` 或 `led_state=on_confirmed`。

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

Phase 2 真实光源后端验收点：

- 缺少 LED/激光通道映射、`frequency_hz`、`duty_percent` 或 `default_off_required: true` 时，`laser_on()` 和 `led_on()` 必须失败，不得写输出状态寄存器。
- 配置电压高于 5.0 V、把 5.0 V 写成 `0x0050`、`station_id=0`、或尝试写 `Reg23`/`Reg24`/`Reg25`/改地址命令时，必须在软件层拒绝。
- 写 `Reg1` 前必须读回 `Reg17-Reg21` 全部为 `0`；若任何 PWM 输出已开启，必须失败或先关闭并读回确认，不得直接修改 `Reg1`。
- 打开通道前必须读回 `Reg1 == 0x0032`、所有通道输出状态、目标通道频率和目标通道占空比；任一读回与配置不匹配都不得进入对应状态。
- 执行 `led_on()` 后 `laser_state` 必须保持非 `on_confirmed`；此时直接执行样品采集必须失败。
- 写 `Reg1` 或输出状态后必须再次用 `0x03` 读回确认；只收到 `0x06` 或 `0x10` 返回帧不算通过。
- 读回帧 CRC 错误、站号不匹配、功能码异常、长度或 byte count 不匹配时，必须视为失败，不得更新光源状态。
- 异常退出路径必须尝试关闭所有已配置光源通道，并读回对应 `Reg17-Reg21` 为 `0`；失败时必须提示人工确认。
- HTTP 后端不能读回电压和输出状态，或允许透传任意 URL/请求体/厂家命令字符串时，不得进入真实光源自动控制验收。

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
- 真实光源控制器接入：已有 PWM Modbus RTU 协议，可在上机确认通道映射和安全联锁后实现；厂家 HTTP API 上线后作为替代后端评估。
- 自动曝光、峰识别、基线校正、批量任务调度。

## 16. 风险和待确认事项

1. 光源控制协议已获取，但仍需确认白光/激光通道映射、实际 COM 口、站号、默认频率/占空比、输出电压是否全通道共享，以及激光安全联锁能否软件读取。
2. 位移台实际分辨率：PDF 示例不一定等于当前实验平台，需要老师或厂家确认丝杆导程、减速比和轴方向。
3. 位移台没有绝对位置读取：软件坐标依赖归零和相对运动账本，断电或手动移动后必须重新归零。
4. Windows DLL 位数：Python 位数必须与 DLL 位数一致，建议统一 64-bit。
5. Zolix Python demo 不能直接复用：存在硬编码 DLL 路径、函数未封装完整、签名错误和函数名错误。
6. Zolix native API 命名不干净：raw 层必须保留真实 symbol，adapter 层必须暴露干净业务名。
7. DField Demo 存在不匹配函数：不能依赖 `a4_set_trigger_mode`。
8. DField SDK 诊断能力弱：无设备 id、无错误码、无版本查询，Phase 1 只能按单相机全局状态 DLL 处理。
9. DField `long*` buffer 只能在 Windows 真实调用语境下解释；跨平台测试必须使用平台无关的数据模型。
10. WayneLabs 协议对命令完整性和超时敏感：必须集中测试命令编码、返回解析、重试策略和坐标状态机。
11. 样品识别算法未定：需要和冯博士确定输入、输出、标定方式和失败策略。
12. MAPS 当前电脑的软件内容稍有差异：上机时需要核对实际硬件连接、串口号、DLL 路径和光源控制方式。
13. 激光功率控制（部分确认）：开/关=PWM；功率=半波片(HWP)，软件可控（师兄的独立程序，接口待拿到），单位 mW、按物镜 Pmin/Pmax、HWP 角度调，初始化会功率波动可能伤样。后续可加独立 HWP 功率适配器（`set_power_mw`，按物镜限幅）；`set_intensity_percent` 不映射 PWM。PWM 通道号查 MAPS 系统配置 mode 页面（Image=LED 开；测试=LED 关、激光开；共 5 通道，可逐个试），上机确认。
14. 我们要做的"Mapping"是**样品盘分层扫描**（对应 §4.4），**不是**仪器栅格 Mapping（SOP §5）。结构：样品盘→格子/晶片→样品。流程：home(机械限位)→按样品盘已知几何到晶片中心→CCD 拍整片→识别给**掩码**→**我们从掩码提取样品中心**→对每个中心做"中心+参数化2个周围点、每点单点 Raman ×2"→每测完一个样品回晶片中心→下一晶片。坐标以**图像中心为原点**（拍照时=位移台当前位置），样品中心像素偏移经像素↔位移台仿射标定换成相对移动；标定随物镜倍率变化。冯博士只给识别图像/掩码，中心提取与数据格式由我们定。待确认：掩码形式、激光斑是否=图像中心、样品盘几何、各物镜标定。MAPS 原生 `.tdms` 是否互通待定。

## 17. 后续 Agent 开发约束

后续 AI Agent 开发时应遵守：

- 不直接操作硬件协议字符串或 native SDK symbol；只有 `src/lab_auto/devices/raw/*` 和对应 raw 层测试可以包含这些内容。
- 不绕过安全层调用激光、归零、长距离移动。
- 任何真实硬件动作都必须可 dry-run。
- 每个实验动作必须写日志。
- 所有实验输出必须保存元数据。
- 新增硬件优先实现 `BaseDevice` 风格接口，再接入工作流。
- 实验工作流应可中断、可恢复、可审计。

## 18. 建议的下一步

下一步应基于本规格文档写实现计划，明确文件结构、开发顺序和测试命令。实现计划通过后，再开始创建 Python 包和 CLI。
