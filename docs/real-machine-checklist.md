# 真机复验清单

2026-06-24 在实验室电脑上验证过设备通信和单点测量。之后的安全修复（2026-07）、可靠性修复（2026-09-07）和交接前精简（2026-10-09）都只在模拟设备上测试过，需要按本清单在真机上复验。

做法：按顺序执行，第 1 节全部通过之前不做后面各节。每项的实测数值写进 [lab-setup.md](lab-setup.md) 第 3 节（配置文件不入库，数值只留在配置里会丢失），与模拟结果不一致的现象写进 [PROJECT_STATUS.md](PROJECT_STATUS.md) 的「已知边界」。

每次真机操作前：操作员在场；物理急停和激光钥匙开关伸手可及；样品台上不放贵重样品；先 `--dry-run`。涉及开激光的步骤先口头告知操作员。

## 0. 环境

- [ ] 按 [lab-setup.md](lab-setup.md) 安装，`pytest -q` 全部通过，记录 Python 版本与测试数量。
- [ ] `python -m serial.tools.list_ports` 的结果与 lab-setup.md 第 3 节的串口表一致。
- [ ] `ramanctl devices doctor --config configs\devices.real.yaml --real` 报告 64 位 Python、两个 DLL 都可加载。

## 1. 激光安全（最优先）

- [ ] **上电复位**：用厂家工具把一个非激光通道打开，再运行任一需要光源的命令或启动后端。判据：全部通道被关闭且读回为 0；后端日志出现 `power-on laser safety reset confirmed`。
- [ ] **开激光前的检查**：把配置中激光通道的频率或占空比改成与控制器不同的值，运行单点测量。判据：拒绝开激光并报 frequency/duty mismatch。改回正确值后可以正常测量。
- [ ] **Reg1**：读取光源状态（Web 设备页或 `GET /api/devices/light/status`）。判据：`voltage_register` 为 50。
- [ ] **测量结束关激光**：单点测量完成后读取光源状态。判据：5 个通道全部为 0。
- [ ] **急停**：短曝光真机测量进行中，点击 Web 全局急停（或 `POST /api/emergency-stop`），同时让浏览器的进度连接断开或卡住。判据：响应 `laser_off: "confirmed"`，激光实际熄灭（目视或功率计），关灯不等待进度推送。软件关灯失败时立即用物理开关。
- [ ] **停止任务**：测量进行中点「停止」。判据：状态依次为 stopping、stopped，激光实际熄灭。
- [ ] **串口失步自愈**：确认 PWM 控制器的串口参数（8N1 或 8E1）；有条件时干扰一次串口。判据：重试后恢复，不会一直停在 `manual_wait`。
- [ ] **参数上限**：配置 `exposure_ms: 60001`。判据：拒绝运行，报错含 `safety cap`。

## 2. 位移台

- [ ] **归零方向**：低速、手放急停上，逐轴观察安全的归零方向，写入 `stage.home_direction`。再用相反方向执行 home。判据：被 SafetyError 拒绝。
- [ ] **分辨率与软限位**：实测每轴每步位移和可用行程，替换配置中的占位值 `resolution_um: 0.04`、`±5000 / ±1000 µm`。
- [ ] **移动中断**：X 轴小行程移动（如 500 µm）途中在任务管理器结束进程，再重新运行。判据：该轴状态为 `unknown`，大距离移动被拒绝，需要重新归零。注意电机会走完剩余行程，先确认行程内无碰撞。
- [ ] **identify 分包**：多次运行 `stage identify`，记录是否出现首个响应不完整导致报错，以及出现频率。

## 3. 光谱仪与相机

- [ ] **波长换算**：短曝光运行 `workflow single --real`。判据：`raw.csv` 有 `wavelength_nm` 列且数值在中心波长附近，`metadata.json` 的 `x_axis_type` 为 `wavelength_nm`。换算失败时测量会失败并关激光，记录报错。
- [ ] **背景扣除**：`corrected.csv` 等于样品值减去 `background.csv` 的实测值。
- [ ] **ROI 边界**：用宽或高不能被 bin 整除的 ROI 采集（如 ROI 宽 7、`bin_x` 2）。判据：返回尺寸正确，进程不崩溃。
- [ ] **ROI 残留**：先做一次 image 模式加 ROI 采集，紧接着 FVB 采集。判据：FVB 长度为 2048。
- [ ] **温度**：`ramanctl camera temperature` 记录环境温度；确认 `a4_set_cooling_temp` 是否可用及到温时间（后续控温功能需要）。

## 4. Web 后端

- [ ] **硬件互斥**：设备诊断进行中提交测量。判据：诊断结束前不打开测量设备；同时发起两次诊断，第二次返回 409。
- [ ] **任务恢复**：刷新浏览器后仍能看到并停止同一任务；重启后端后，未完成任务显示为失败，不会自动继续曝光，已完成结果仍可查看。
- [ ] **失败留档**：拔掉相机或取消测量。判据：输出目录里的 `metadata.json` 和 `run.log` 写明原因，历史页显示真实状态。
- [ ] **科研记录**：填写实际 `excitation_wavelength_nm` 和样品处实测 `laser_power_mw`。判据：输出中有配置快照、软件版本、探测器温度和这两个值。

## 5. 托盘扫描

- [ ] **激光斑与图像中心**：按 lab-setup.md 第 6 节测量并填写标定。
- [ ] **识别握手**：按 [recognition-handoff.md](recognition-handoff.md) 的验收判据，先用模拟采集端测试错 session、旧时间、错摘要、错尺寸、取消和 `measurement_ready: false` 的拒绝情况。
- [ ] **参数检查**：不带 `--recognition-dir` / `--session-id` 运行 `scan tray --real`。判据：在打开设备前报错。
- [ ] **废样品试跑**：光路恢复和标定都验证后，用废样品、一个盘格试跑，再逐步增加盘格数。

## 6. 尚未接入的串口设备

- [ ] 物镜转盘（COM5）、光路切换（COM16）、半波片（COM17）：**不要向身份未确认的串口发送任何指令**。先向老师或师兄要旧控制代码（`lenschange.py`、`changelight.py`、`lasermove.py`），确认波特率、指令和响应格式，记录到 lab-setup.md，供以后接入。
