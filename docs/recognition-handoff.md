# 托盘扫描：外部采集与识别文件握手

本文写给开发外部拍照/识别程序的人，以及运行真机托盘扫描的人。

托盘扫描每到一片晶圆中心，本项目就在共享目录里写一个请求文件；外部程序看到请求后切换光路、拍照、用识别模型生成样品掩码，再写回一个回执文件。本项目校验回执后，根据掩码中样品的位置移动位移台测量。相机拍照、识别模型和光路切换都由外部程序或操作员完成，本仓库不包含识别模型，也不控制 COM16/COM17/COM5。Web 只提供预演，不启动真实托盘扫描。

## 真机前提

- 操作员在场，物理急停可用。API、CLI、厂家软件只能有一个硬件控制进程运行。
- 已完成当前版本的 `real-machine-checklist.md`；X/Y 原点、限位、托盘几何、物镜与激光斑位置经过实测。
- `calibration.image_width_px` 和 `image_height_px` 必须填写实际标定图像尺寸。采集图与掩码必须使用同一像素坐标系，不能直接使用缩放/裁剪后的模型输出。
- 外部采集程序只能在收到本次盘格请求后拍照；拍照时激光关闭，完成后恢复并核实测量光路，才可写 `measurement_ready: true`。此字段是外部程序/操作员的确认，不是本项目对 COM16 的硬件读回。
- 两台机器同步时钟，使用带时区的 ISO 时间。共享目录需支持同目录原子重命名，已发布的图像和回执不能再修改。
- 安装 `pip install -e ".[dev,api]"`。

## 启动

先预演：

```bash
ramanctl scan tray --config configs/tray_scan.real.yaml --dry-run
```

完成现场确认后，CLI 可使用以下命令。`session-id` 标识一次真实装盘；换盘、重新归零、移动样品或改变标定必须使用新 session 和新输出目录。

```bash
ramanctl scan tray --config configs/tray_scan.real.yaml --devices-config configs/devices.real.yaml --real --recognition-dir output/recognition --session-id tray-20260907-001 --recognition-timeout-s 60
```

中断后只允许在样品、坐标原点、配置均未改变时，用同一 session 和输出目录恢复。软件检查配置指纹；原点及样品是否真的未变化仍需现场确认。

## 请求与回执

位移台到达盘格中心后，CLI 原子写入 `<recognition-dir>/<session-id>/<index>.request.json`。每次请求都有新的随机 `request_id`，包含：

- `session_id`、`request_id`、`requested_at`。
- `wafer`：`index`、`row`、`col`、`x_um`、`y_um`。
- `calibration`：物镜、矩阵、图像中心及尺寸。
- `capture_file`、`mask_file`、`response_file`：本次图像和回执的文件名。

外部程序读取请求，重新拍照并识别，按请求指定的文件名保存原图和二值 PNG 掩码。图像先写临时文件再重命名，最后原子发布回执。回执示例：

```json
{
  "session_id": "tray-20260907-001",
  "request_id": "复制本次请求的 request_id",
  "wafer_index": 0,
  "captured_at": "2026-09-07T10:00:01+08:00",
  "objective": "50x",
  "capture_sha256": "实际原图文件字节的 SHA-256",
  "mask_sha256": "实际掩码文件字节的 SHA-256",
  "measurement_ready": true
}
```

`captured_at` 必须是本次照片的实际拍摄时间，不能复制请求时间或给旧图重新打时间戳。检查摘要使用 `hashlib.sha256(path.read_bytes()).hexdigest()`。掩码白色是样品、黑色是背景。

回执缺失时默认等待 60 秒，可配置至 300 秒；取消会中断等待。错误回执、旧时间、物镜不符、文件摘要不符、原图/掩码尺寸不符都会终止扫描，不进入该盘格的激光测量。被接受的回执保存在 `manifest.json` 对应盘格中。

## 验收判据

1. 使用模拟位移台和模拟采集端完成一次请求→回执→测点规划，确认请求编号及产物记录一致。
2. 注入旧 session、错 request_id、错盘格、旧拍摄时间、错误摘要、`measurement_ready: false`：全部拒绝。
3. 原图或掩码尺寸与标定不符：拒绝测量；缺标定尺寸：在位移台移动和任何激光动作前拒绝。
4. 不提交回执或中途取消：超时/取消可退出，已完成测点记录保留。
5. 真机只在废样品上验证光路恢复、激光斑对准和重复定位，再逐步扩展盘格数。

烧检在启用背景扣除时使用 `corrected.csv`，否则使用 `raw.csv`。饱和、非有限值或零参考信号不能得出正常结论；阈值需按同一数据处理方式重新实测。烧检是重复谱变化提示，不能单独证明物理烧伤。
