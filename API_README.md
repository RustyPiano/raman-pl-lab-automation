# FastAPI Backend for Raman/PL Lab Automation

## 快速启动

### 1. 安装依赖

```bash
# 激活虚拟环境
source .venv/bin/activate
pip install -e ".[api]"
```

### 2. 启动服务器

**方法 1：使用启动脚本（推荐）**
```bash
./scripts/start_api.sh
```

**方法 2：直接使用 uvicorn**
```bash
cd /path/to/Raman自动化
source .venv/bin/activate
export PYTHONPATH=src
uvicorn lab_auto.api.main:app --host 127.0.0.1 --port 8008
```

### 3. 访问 API

- **Swagger 文档**: http://127.0.0.1:8008/docs
- **ReDoc 文档**: http://127.0.0.1:8008/redoc
- **健康检查**: http://127.0.0.1:8008/health

## API 端点

### 设备管理 (`/api/devices`)

- `GET /api/devices/status` - 获取所有设备状态（任务运行中返回 409）
- `POST /api/devices/scan` - 扫描可用设备（任务运行中返回 409）
- `GET /api/devices/light/status` - 获取激光/LED 状态（只读寄存器回读，不写任何通道；任务运行中返回 409）
- `POST /api/devices/light/off` - 强制关闭全部光源通道（读回确认；任务运行中会先取消所有任务再关灯）

> 注意：`POST /api/devices/light/on` 已移除。无认证的裸激光开启端点是 CSRF 攻击面；
> 激光只能通过带确认的工作流（`mode="real"` + `confirm_real=true`）开启。

### 系统安全 (`/api`)

- `POST /api/emergency-stop` - 软件级紧急停止：取消所有任务 + 尽力强制关闭光源。
  响应中的 `laser_off` 字段如实报告 `confirmed` / `failed: <原因>` / `not_applicable`；
  失败时请立即使用物理开关。软件急停不能替代物理急停按钮。

### 配置管理 (`/api/configs`)

- `GET /api/configs?config_type=all|single_point|tray` - 按类型列出配置文件；`tray` 只返回通过完整校验的配置
- `GET /api/configs/{name}` - 读取指定配置文件
- `POST /api/configs/validate` - 验证配置文件

### 工作流执行 (`/api/workflow`)

- `POST /api/workflow/single-point` - 启动单点 Raman 测量
- `POST /api/workflow/tray/preview` - 生成无硬件副作用的托盘 dry-run 计划（几何、动作和统计）
- `GET /api/workflow/jobs` - 列出所有任务
- `GET /api/workflow/jobs/{job_id}` - 获取任务详情
- `POST /api/workflow/jobs/{job_id}/stop` - 停止任务（协作式取消：pending 立即停止；
  running 进入 `stopping` 状态，工作流在下一个检查点安全收尾（含强制关激光）后才变为 `stopped`）
- `WS /api/workflow/ws/jobs/{job_id}` - WebSocket 实时进度推送

### 历史结果 (`/api/history`)

- `GET /api/history` - 列出 `output/measurements` 中有效的持久化单点结果
- `GET /api/history/{record_id}` - 读取元数据与可绘图光谱
- `GET /api/history/{record_id}/files/{filename}` - 下载该结果的 CSV、JSON 或运行日志

## 使用示例

### 1. 启动单点测量（模拟模式）

```bash
curl -X POST http://127.0.0.1:8008/api/workflow/single-point \
  -H "Content-Type: application/json" \
  -d '{
    "config_path": "single_point.example.yaml",
    "mode": "simulated"
  }'
```

未传 `mode` 时默认使用 `dry_run`。真机模式必须显式确认：

```bash
curl -X POST http://127.0.0.1:8008/api/workflow/single-point \
  -H "Content-Type: application/json" \
  -d '{
    "config_path": "single_point.example.yaml",
    "mode": "real",
    "confirm_real": true
  }'
```

响应：
```json
{
  "id": "abc-123-def",
  "type": "single_point",
  "status": "pending",
  "progress": {
    "current_step": null,
    "total_steps": null,
    "completed_steps": 0,
    "message": null,
    "percentage": null
  },
  "created_at": "2026-07-01T00:00:00Z"
}
```

### 2. 查询任务状态

```bash
curl http://127.0.0.1:8008/api/workflow/jobs/{job_id}
```

### 3. WebSocket 连接（实时进度）

```javascript
const ws = new WebSocket('ws://127.0.0.1:8008/api/workflow/ws/jobs/{job_id}');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Progress:', data);
  
  if (data.type === 'progress') {
    console.log(`Step: ${data.step}, ${data.percentage}%`);
  } else if (data.type === 'status') {
    console.log(`Status: ${data.status}`);
  } else if (data.type === 'error') {
    console.error('Error:', data.error);
  }
};

// 保持连接
setInterval(() => ws.send('ping'), 30000);
```

### 4. 扫描设备

```bash
curl -X POST http://127.0.0.1:8008/api/devices/scan \
  -H "Content-Type: application/json"
```

### 5. 列出配置文件

```bash
curl http://127.0.0.1:8008/api/configs
```

## 架构说明

### 核心组件

1. **main.py** - FastAPI 应用入口，路由挂载，CORS 配置
2. **models.py** - Pydantic 数据模型（请求/响应）
3. **task_queue.py** - 单线程任务队列（确保硬件安全）
4. **websocket.py** - WebSocket 连接管理器（实时进度推送）
5. **routers/** - API 路由模块
   - `devices.py` - 设备管理
   - `configs.py` - 配置管理
   - `workflow.py` - 工作流执行

### 设计原则

1. **单线程执行**：所有硬件操作通过 `TaskQueue` 串行执行，防止并发激光操作
2. **异步架构**：使用 FastAPI 异步特性，工作流在线程池中执行
3. **实时推送**：通过 WebSocket 广播进度，支持多客户端订阅
4. **错误处理**：捕获 `ConfigError`, `DeviceError`, `SafetyError`，返回友好的 HTTP 错误
5. **复用现有代码**：直接调用 `devices/`, `workflow/` 模块，不修改现有逻辑

### 安全机制

- 任务队列确保同一时间只有一个硬件操作
- Web API 默认 `dry_run`，`mode=real` 必须带 `confirm_real=true`
- 激光开关需要通过设备层的安全检查
- 配置验证在任务启动前执行
- WebSocket 连接自动清理断开的客户端

## 开发说明

### 添加新端点

1. 在 `routers/` 中创建新的路由模块
2. 在 `main.py` 中挂载路由：
   ```python
   from lab_auto.api.routers import new_router
   app.include_router(new_router.router)
   ```

### 扩展任务类型

在 `task_queue.py` 中添加新的任务执行方法：

```python
async def submit_new_task(self, job_id: str, **kwargs):
    await self._queue.put({
        "job_id": job_id,
        "type": "new_task",
        **kwargs
    })

async def _execute_new_task(self, job_id: str, **kwargs):
    # 实现任务逻辑
    pass
```

### 日志配置

日志输出到控制台，可在 `main.py` 中调整级别：

```python
logging.basicConfig(level=logging.DEBUG)  # 更详细的日志
```

## 故障排查

### 端口已占用

```bash
# 查找占用端口的进程
lsof -ti:8008

# 终止进程
kill $(lsof -ti:8008)
```

### 导入错误

确保 `PYTHONPATH` 包含 `src` 目录：

```bash
export PYTHONPATH=/path/to/Raman自动化/src
```

### WebSocket 连接失败

检查 CORS 配置是否允许前端域名（`main.py` 中的 `allow_origins`）

## 下一步

- [ ] 添加身份验证（JWT）
- [ ] 添加速率限制
- [ ] 实现任务持久化（数据库）
- [ ] 添加任务取消机制（优雅停止）
- [ ] 集成 Prometheus metrics
- [ ] Docker 容器化部署
