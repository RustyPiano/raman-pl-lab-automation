import { useEffect, useState } from 'react';
import { Link, Outlet, useLocation } from 'react-router-dom';
import {
  Beaker,
  CircleCheck,
  CircleDotDashed,
  CircleX,
  Database,
  LayoutGrid,
  MonitorCog,
  OctagonAlert,
  ScanLine,
} from 'lucide-react';
import { toast } from 'sonner';

import apiClient, { getErrorMessage } from '@/api/client';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

const navItems = [
  { path: '/', label: '单点测量', shortLabel: '单点', icon: ScanLine },
  { path: '/tray', label: '托盘扫描', shortLabel: '托盘', icon: LayoutGrid },
  { path: '/devices', label: '设备监控', shortLabel: '设备', icon: MonitorCog },
  { path: '/history', label: '历史记录', shortLabel: '历史', icon: Database },
];

export function App() {
  const location = useLocation();
  const [apiStatus, setApiStatus] = useState<'checking' | 'online' | 'offline'>('checking');
  const [showEmergencyDialog, setShowEmergencyDialog] = useState(false);
  const [isStopping, setIsStopping] = useState(false);

  useEffect(() => {
    let active = true;
    const checkHealth = () => {
      apiClient.getHealth()
        .then(() => { if (active) setApiStatus('online'); })
        .catch(() => { if (active) setApiStatus('offline'); });
    };
    checkHealth();
    const timer = window.setInterval(checkHealth, 15_000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, []);

  const handleEmergencyStop = async () => {
    setIsStopping(true);
    try {
      const { data } = await apiClient.emergencyStop();
      if (data.laser_off.startsWith('failed')) {
        toast.error(data.message ?? '软件无法确认激光已关闭，请立即使用物理急停开关');
      } else {
        const lightStatus = data.laser_off === 'confirmed' ? '已确认关闭' : data.laser_off === 'not_applicable' ? '无需软件控制' : data.laser_off;
        toast.success(`急停已执行：取消 ${data.jobs_cancelled.length} 个任务，光源${lightStatus}`);
      }
      setShowEmergencyDialog(false);
    } catch (error) {
      toast.error(`软件急停请求失败：${getErrorMessage(error)}。请立即使用物理急停开关。`);
    } finally {
      setIsStopping(false);
    }
  };

  const currentPageLabel = navItems.find((item) => item.path === location.pathname)?.label ?? '单点测量';
  const statusLabel = apiStatus === 'online' ? 'API 已连接' : apiStatus === 'offline' ? 'API 未连接' : '检查 API';
  const ApiStatusIcon = apiStatus === 'online' ? CircleCheck : apiStatus === 'offline' ? CircleX : CircleDotDashed;

  return (
    <div className="min-h-screen bg-background">
      <aside className="fixed inset-y-0 left-0 hidden w-60 flex-col border-r bg-card lg:flex">
        <Link to="/" className="flex h-20 items-center gap-3 border-b px-6">
          <span className="flex size-10 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <Beaker aria-hidden="true" className="size-5" />
          </span>
          <span>
            <span className="block font-semibold tracking-tight">Raman/PL</span>
            <span className="block text-xs text-muted-foreground">实验自动化控制台</span>
          </span>
        </Link>

        <nav aria-label="主导航" className="flex flex-1 flex-col gap-1 p-3">
          {navItems.map((item) => {
            const Icon = item.icon;
            const active = location.pathname === item.path;
            return (
              <Link
                key={item.path}
                to={item.path}
                aria-current={active ? 'page' : undefined}
                className={cn(
                  'flex min-h-11 items-center gap-3 rounded-md px-3 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset',
                  active
                    ? 'bg-primary text-primary-foreground'
                    : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground',
                )}
              >
                <Icon aria-hidden="true" className="size-5" />
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="flex flex-col gap-3 border-t p-4">
          <Badge variant={apiStatus === 'offline' ? 'destructive' : apiStatus === 'online' ? 'secondary' : 'outline'} className="w-fit gap-1.5">
            <ApiStatusIcon aria-hidden="true" />
            {statusLabel}
          </Badge>
          <Button variant="destructive" onClick={() => setShowEmergencyDialog(true)}>
            <OctagonAlert data-icon="inline-start" />
            软件急停
          </Button>
          <p className="text-xs leading-relaxed text-muted-foreground">软件急停不能替代实验台物理急停。</p>
        </div>
      </aside>

      <div className="flex min-h-screen flex-col lg:pl-60">
        <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b bg-card/95 px-4 backdrop-blur sm:px-6 lg:px-8">
          <div className="flex items-center gap-3">
            <span className="flex size-9 items-center justify-center rounded-md bg-primary text-primary-foreground lg:hidden">
              <Beaker aria-hidden="true" className="size-5" />
            </span>
            <div>
              <p className="font-semibold tracking-tight lg:text-lg"><span className="lg:hidden">Raman/PL</span><span className="hidden lg:inline">{currentPageLabel}</span></p>
              <p className="hidden text-xs text-muted-foreground sm:block">Raman/PL 实验自动化控制台</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant={apiStatus === 'offline' ? 'destructive' : apiStatus === 'online' ? 'secondary' : 'outline'} className="gap-1.5 lg:hidden">
              <ApiStatusIcon aria-hidden="true" />
              <span className="sm:hidden">{apiStatus === 'online' ? '在线' : apiStatus === 'offline' ? '离线' : '检查中'}</span>
              <span className="hidden sm:inline">{statusLabel}</span>
            </Badge>
            <Button variant="destructive" size="sm" onClick={() => setShowEmergencyDialog(true)}>
              <OctagonAlert data-icon="inline-start" />
              急停
            </Button>
          </div>
        </header>

        <main className="flex-1 pb-24 lg:pb-0">
          <Outlet />
        </main>

        <footer className="hidden border-t bg-card px-8 py-3 text-xs text-muted-foreground lg:flex lg:items-center lg:justify-between">
          <span>本地实验控制 · 默认安全模式</span>
          <span>v0.1.0</span>
        </footer>
      </div>

      <nav aria-label="移动端主导航" className="fixed inset-x-0 bottom-0 z-30 grid h-20 grid-cols-4 border-t bg-card px-2 pb-[env(safe-area-inset-bottom)] lg:hidden">
        {navItems.map((item) => {
          const Icon = item.icon;
          const active = location.pathname === item.path;
          return (
            <Link
              key={item.path}
              to={item.path}
              aria-current={active ? 'page' : undefined}
              className={cn(
                'flex min-h-14 flex-col items-center justify-center gap-1 rounded-md text-xs font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset',
                active ? 'text-primary' : 'text-muted-foreground',
              )}
            >
              <Icon aria-hidden="true" className="size-5" />
              {item.shortLabel}
            </Link>
          );
        })}
      </nav>

      <AlertDialog open={showEmergencyDialog} onOpenChange={setShowEmergencyDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2">
              <OctagonAlert aria-hidden="true" />
              执行软件急停？
            </AlertDialogTitle>
            <AlertDialogDescription>
              系统会取消所有未完成任务并尝试关闭全部光源。若软件无法确认激光已关闭，请立即使用实验台物理急停开关。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isStopping}>取消</AlertDialogCancel>
            <AlertDialogAction variant="destructive" disabled={isStopping} onClick={(event) => {
              event.preventDefault();
              void handleEmergencyStop();
            }}>
              {isStopping ? '正在执行…' : '确认急停'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

export default App;
