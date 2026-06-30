import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { Toaster } from '@/components/ui/sonner'
import './index.css'
import App from './App.tsx'
import { SinglePoint } from '@/views/SinglePoint'
import { TrayScanning } from '@/views/TrayScanning'
import { DeviceMonitoring } from '@/views/DeviceMonitoring'
import { History } from '@/views/History'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<App />}>
          <Route index element={<SinglePoint />} />
          <Route path="tray" element={<TrayScanning />} />
          <Route path="devices" element={<DeviceMonitoring />} />
          <Route path="history" element={<History />} />
        </Route>
      </Routes>
      <Toaster />
    </BrowserRouter>
  </StrictMode>,
)
