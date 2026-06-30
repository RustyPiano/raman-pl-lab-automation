import { Outlet, Link, useLocation } from 'react-router-dom';
import { cn } from '@/lib/utils';
import { Beaker } from 'lucide-react';

export function App() {
  const location = useLocation();

  const navItems = [
    { path: '/', label: '单点测量' },
    { path: '/tray', label: '托盘扫描' },
    { path: '/devices', label: '设备监控' },
    { path: '/history', label: '历史记录' },
  ];

  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="border-b bg-white sticky top-0 z-50">
        <div className="container mx-auto px-4">
          <div className="flex items-center justify-between h-16">
            {/* Logo */}
            <Link to="/" className="flex items-center gap-2 font-semibold text-lg">
              <Beaker className="h-6 w-6 text-primary" />
              <span>Raman/PL 实验平台</span>
            </Link>

            {/* Navigation */}
            <nav className="flex items-center gap-1">
              {navItems.map((item) => (
                <Link
                  key={item.path}
                  to={item.path}
                  className={cn(
                    'px-4 py-2 rounded-md text-sm font-medium transition-colors',
                    location.pathname === item.path
                      ? 'bg-primary text-primary-foreground'
                      : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground'
                  )}
                >
                  {item.label}
                </Link>
              ))}
            </nav>
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="flex-1 bg-slate-50">
        <Outlet />
      </main>

      {/* Footer status bar */}
      <footer className="border-t bg-white">
        <div className="container mx-auto px-4 py-2">
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <div className="flex items-center gap-4">
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-green-500"></span>
                API 已连接
              </span>
            </div>
            <div>
              Raman/PL 自主实验平台 v0.1.0
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}

export default App;

