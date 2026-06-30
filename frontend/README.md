# Raman/PL 实验平台前端

基于 React + Vite + TypeScript + shadcn/ui 构建的现代化实验室操作界面。

## 技术栈

- **React 19** - UI 框架
- **TypeScript** - 类型安全
- **Vite** - 构建工具
- **Tailwind CSS** - 样式框架
- **shadcn/ui** - UI 组件库
- **Zustand** - 状态管理
- **React Router** - 路由管理
- **Recharts** - 数据可视化
- **Axios** - HTTP 客户端

## 快速开始

### 安装依赖

```bash
npm install
```

### 开发模式

```bash
npm run dev
```

访问 `http://localhost:5173` 查看应用。

### 构建生产版本

```bash
npm run build
```

生成的文件在 `dist/` 目录。

## 功能特性

### ✅ Phase A 已完成

#### 单点测量
- 配置文件选择
- 运行模式切换（dry_run/simulated/real）
- 单点参数由 YAML 配置驱动
- 实时进度显示
- WebSocket 实时更新
- 光谱图表展示
- real 模式显式安全确认

### 🚧 Phase B 待开发

- 托盘扫描
- 设备监控
- 历史记录

## 项目结构

```
frontend/
├── src/
│   ├── api/
│   │   └── client.ts          # API 客户端封装
│   ├── components/
│   │   ├── ui/                # shadcn/ui 组件
│   │   ├── SafetyConfirm.tsx  # 安全确认对话框
│   │   ├── ProgressDisplay.tsx # 进度显示
│   │   └── SpectrumChart.tsx  # 光谱图表
│   ├── stores/
│   │   └── workflowStore.ts   # 工作流状态管理
│   ├── views/
│   │   ├── SinglePoint.tsx    # 单点测量页面
│   │   ├── TrayScanning.tsx   # 托盘扫描（占位）
│   │   ├── DeviceMonitoring.tsx # 设备监控（占位）
│   │   └── History.tsx        # 历史记录（占位）
│   ├── lib/
│   │   └── utils.ts           # 工具函数
│   ├── App.tsx                # 主应用组件
│   ├── main.tsx               # 应用入口
│   └── index.css              # 全局样式
├── components.json            # shadcn/ui 配置
├── tailwind.config.js         # Tailwind 配置
├── vite.config.ts             # Vite 配置
└── package.json
```

## API 集成

前端通过以下方式与后端通信：

### HTTP API
- **基础 URL**: `/api`（通过 Vite 代理到 `http://127.0.0.1:8008/api`）
- **端点**:
  - `GET /configs` - 获取配置列表
  - `GET /configs/{name}` - 获取特定配置
  - `POST /workflow/single-point` - 启动单点测量（请求体使用 `config_path`、`mode`、可选 `devices_path`；real 模式还需要 `confirm_real=true`）
  - `GET /workflow/jobs/{job_id}` - 获取任务状态
  - `POST /workflow/jobs/{job_id}/stop` - 停止任务

### WebSocket
- **URL**: `ws://127.0.0.1:8008/api/workflow/ws/jobs/{job_id}`
- **用途**: 实时接收任务进度更新

## 配置

### Vite 代理配置

`vite.config.ts` 已配置代理，自动转发请求到后端：

```typescript
proxy: {
  '/api': {
    target: 'http://127.0.0.1:8008',
    changeOrigin: true,
    ws: true,
  }
}
```

### 主题颜色

延用项目配色方案：

```css
--teal: #0f766e;    /* 主色 */
--green: #138a62;   /* 成功 */
--amber: #b77a1f;   /* 警告 */
--red: #bf3d45;     /* 危险 */
```

## 开发指南

### 添加新的 shadcn/ui 组件

```bash
npx shadcn@latest add [component-name]
```

### 状态管理

使用 Zustand store (`workflowStore.ts`)：

```typescript
import { useWorkflowStore } from '@/stores/workflowStore';

function MyComponent() {
  const { currentJob, startSinglePoint } = useWorkflowStore();
  // ...
}
```

### 添加新页面

1. 在 `src/views/` 创建新组件
2. 在 `src/main.tsx` 添加路由
3. 在 `src/App.tsx` 导航栏添加链接

## 安全特性

- **默认 dry-run**: API 默认不会进入真机模式
- **激光安全确认**: Real 模式必须在请求中显式发送 `confirm_real=true`
- **实时反馈**: 所有操作都有即时的加载状态和错误提示
- **WebSocket 重连**: 连接断开后自动重试（3 秒后）

## 浏览器支持

- Chrome/Edge (推荐)
- Firefox
- Safari

## 许可证

内部项目
