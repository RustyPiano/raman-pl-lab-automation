# 前端快速测试指南

## 当前状态

✅ 开发服务器已启动: http://localhost:5173

## 测试步骤

### 1. 访问应用

在浏览器中打开: http://localhost:5173

你应该能看到：
- 顶部导航栏：Logo + 四个导航链接
- 单点测量页面（默认页面）
- 底部状态栏

### 2. 测试单点测量流程

#### 前提条件
确保后端 API 正在运行：
```bash
cd /Users/rustypiano/Documents/研究生/自主实验平台
uvicorn src.lab_auto.api.app:app --host 127.0.0.1 --port 8008 --reload
```

#### 测试流程

1. **选择配置**
   - 从下拉菜单选择一个配置文件（如 `single_point_default.yaml`）
   
2. **选择运行模式**
   - Dry Run: 不连接硬件，只打印日志
   - Simulated: 模拟硬件行为
   - Real: 真机运行（需要安全确认）

3. **填写参数覆盖（可选）**
   - 样品 ID
   - 操作员名称
   - 背景扣除开关

4. **启动测量**
   - 点击"开始测量"按钮
   - 如果是 Real 模式，会弹出安全确认对话框
   - 确认后任务开始运行

5. **观察实时进度**
   - 进度条显示完成百分比
   - 日志窗口显示实时消息
   - 可以点击"停止测量"中止任务

6. **查看结果**
   - 任务完成后自动显示光谱图
   - 可以切换原始/校正光谱
   - 查看元数据和警告信息

### 3. 测试 WebSocket 连接

WebSocket 应该自动连接并接收更新：
- 连接成功: 日志显示 "🔗 Connected to job stream"
- 接收更新: 进度条和日志实时更新
- 连接断开: 自动重连（3 秒后）

### 4. 测试其他页面

点击顶部导航链接：
- 托盘扫描 - 显示"功能开发中"
- 设备监控 - 显示"功能开发中"
- 历史记录 - 显示"功能开发中"

## 预期行为

### ✅ 正常情况
- 配置列表正确加载
- 启动任务返回 job_id
- WebSocket 连接成功
- 进度实时更新
- 任务完成后显示光谱图

### ❌ 错误处理
- 后端未运行: Toast 显示 "加载配置失败"
- 网络错误: Toast 显示错误消息
- WebSocket 断开: 自动重连

## 故障排查

### 1. 配置加载失败
**症状**: 配置下拉菜单为空，Toast 显示错误

**解决方案**:
```bash
# 检查后端是否运行
curl http://127.0.0.1:8008/api/configs

# 如果返回 404 或连接失败，启动后端
cd /Users/rustypiano/Documents/研究生/自主实验平台
uvicorn src.lab_auto.api.app:app --host 127.0.0.1 --port 8008
```

### 2. WebSocket 连接失败
**症状**: 日志显示 "❌ Connection error"

**可能原因**:
- 后端 WebSocket 端点未实现
- 端口被防火墙阻止
- 浏览器不支持 WebSocket

**检查方法**:
```javascript
// 在浏览器控制台运行
const ws = new WebSocket('ws://localhost:8008/ws/jobs/test-123');
ws.onopen = () => console.log('Connected');
ws.onerror = (e) => console.error('Error:', e);
```

### 3. CORS 错误
**症状**: 浏览器控制台显示 CORS 错误

**解决方案**: 后端需要配置 CORS
```python
# 在 app.py 中添加
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 4. 光谱图不显示
**症状**: 任务完成但没有图表

**检查**:
- 打开浏览器开发者工具（F12）
- 查看 Console 是否有错误
- 检查 Network 标签，确认 API 返回了 `result.spectrum` 数据

## 开发工具

### 浏览器开发者工具
- **Console**: 查看日志和错误
- **Network**: 监控 API 请求和 WebSocket 连接
- **React DevTools**: 检查组件状态（需要安装扩展）

### Vite 热重载
修改代码后自动刷新，无需重启服务器。

### Zustand DevTools
```bash
# 安装 Redux DevTools 浏览器扩展
# Zustand store 会自动出现在 Redux DevTools 中
```

## 下一步

### Phase B 功能
1. **托盘扫描**
   - 托盘网格可视化
   - 批量任务管理
   - 进度总览

2. **设备监控**
   - 实时设备状态
   - 激光功率监控
   - 温度/湿度显示

3. **历史记录**
   - 任务列表
   - 结果查询
   - 数据导出

### 性能优化
- 虚拟滚动（大量日志）
- 图表懒加载
- 数据缓存

### 用户体验
- 深色模式
- 键盘快捷键
- 离线提示

## 反馈

如有问题或建议，请记录：
- 重现步骤
- 预期行为 vs 实际行为
- 浏览器版本
- 控制台错误信息
