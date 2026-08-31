/* oxlint-disable react/only-export-components */
import { lazy, StrictMode, Suspense } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, Route, Routes } from 'react-router-dom';

import { Skeleton } from '@/components/ui/skeleton';
import { Toaster } from '@/components/ui/sonner';
import App from './App.tsx';
import './index.css';

const SinglePoint = lazy(() => import('@/views/SinglePoint').then((module) => ({ default: module.SinglePoint })));
const TrayScanning = lazy(() => import('@/views/TrayScanning').then((module) => ({ default: module.TrayScanning })));
const DeviceMonitoring = lazy(() => import('@/views/DeviceMonitoring').then((module) => ({ default: module.DeviceMonitoring })));
const History = lazy(() => import('@/views/History').then((module) => ({ default: module.History })));
const fallback = <div className="mx-auto w-full max-w-[1480px] px-4 py-6 sm:px-6 lg:px-8 lg:py-8"><Skeleton className="h-[560px]" /></div>;

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<App />}>
          <Route index element={<Suspense fallback={fallback}><SinglePoint /></Suspense>} />
          <Route path="tray" element={<Suspense fallback={fallback}><TrayScanning /></Suspense>} />
          <Route path="devices" element={<Suspense fallback={fallback}><DeviceMonitoring /></Suspense>} />
          <Route path="history" element={<Suspense fallback={fallback}><History /></Suspense>} />
        </Route>
      </Routes>
      <Toaster closeButton richColors />
    </BrowserRouter>
  </StrictMode>,
);
