import { useEffect, useState } from 'react';
import type { LucideIcon } from 'lucide-react';
import { Camera, Lightbulb, RefreshCw, ScanSearch, SlidersHorizontal, TriangleAlert, Waves } from 'lucide-react';
import { toast } from 'sonner';

import apiClient, { getErrorMessage } from '@/api/client';
import type { DeviceStatus, LightStatus } from '@/api/client';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
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
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';

type BadgeVariant = 'default' | 'secondary' | 'outline' | 'destructive';

interface DeviceRowProps {
  icon: LucideIcon;
  name: string;
  description: string;
  status: string;
  variant: BadgeVariant;
}

function DeviceRow({ icon: Icon, name, description, status, variant }: DeviceRowProps) {
  return (
    <div className="grid gap-4 border-b p-5 last:border-b-0 sm:grid-cols-[auto_minmax(0,1fr)_auto] sm:items-center">
      <span className="flex size-10 items-center justify-center rounded-lg bg-muted"><Icon aria-hidden="true" className="size-5" /></span>
      <div className="flex min-w-0 flex-col gap-1">
        <p className="font-medium">{name}</p>
        <p className="text-sm text-muted-foreground">{description}</p>
      </div>
      <Badge variant={variant} className="w-fit">{status}</Badge>
    </div>
  );
}

const diagnosticLabels: Record<string, string> = {
  python_64bit: 'Python 64 位',
  stage_port: '位移台配置端口',
  zolix_dll_exists: 'Zolix SDK 文件',
  zolix_ftd2xx_exists: 'FTDI 驱动文件',
  zolix_loadable: 'Zolix SDK 可加载',
  dfield_dll_exists: 'DField SDK 文件',
  dfield_loadable: 'DField SDK 可加载',
};

function formatValue(value: unknown) {
  if (typeof value === 'boolean') return value ? '通过' : '未通过';
  if (value === null || value === undefined || value === '') return '无';
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

export function DeviceMonitoring() {
  const [status, setStatus] = useState<DeviceStatus | null>(null);
  const [light, setLight] = useState<LightStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [turningOff, setTurningOff] = useState(false);
  const [showOffDialog, setShowOffDialog] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadStatus = async (quiet = false) => {
    if (!quiet) setRefreshing(true);
    setError(null);
    try {
      const [deviceResult, lightResult] = await Promise.allSettled([
        apiClient.getDeviceStatus(),
        apiClient.getLightStatus(),
      ]);
      const errors: string[] = [];
      if (deviceResult.status === 'fulfilled') setStatus(deviceResult.value.data);
      else errors.push(`设备诊断：${getErrorMessage(deviceResult.reason)}`);
      if (lightResult.status === 'fulfilled') setLight(lightResult.value.data);
      else errors.push(`光源状态：${getErrorMessage(lightResult.reason)}`);
      setError(errors.length > 0 ? errors.join('；') : null);
    } catch (loadError) {
      setError(getErrorMessage(loadError));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    void loadStatus(true);
  }, []);

  const handleScan = async () => {
    setScanning(true);
    setError(null);
    try {
      const response = await apiClient.scanDevices();
      setStatus((current) => current
        ? { ...current, runtime_mode: response.data.runtime_mode, scan: response.data }
        : current);
      if (!status) await loadStatus(true);
      toast.success('设备扫描已完成');
    } catch (scanError) {
      setError(getErrorMessage(scanError));
      toast.error(`设备扫描失败：${getErrorMessage(scanError)}`);
    } finally {
      setScanning(false);
    }
  };

  const handleLightOff = async () => {
    setTurningOff(true);
    try {
      const response = await apiClient.turnLightOff();
      if (response.data.status === 'manual') toast.info(response.data.message);
      else toast.success(response.data.message);
      setShowOffDialog(false);
      await loadStatus(true);
    } catch (offError) {
      toast.error(`关闭光源失败：${getErrorMessage(offError)}`);
    } finally {
      setTurningOff(false);
    }
  };

  const realMode = status?.runtime_mode === 'real';
  const stageError = status?.scan.waynelabs.error;
  const stageConnected = Boolean(status?.scan.waynelabs.device);
  const spectrometerConnected = (status?.scan.zolix_devices.length ?? 0) > 0;
  const cameraConnected = Boolean(status?.scan.dfield_available);
  const laserState = light?.hardware_state?.laser_state;
  const lightDanger = typeof laserState === 'string' && !laserState.includes('off');

  return (
    <div className="mx-auto flex w-full max-w-[1480px] flex-col gap-6 px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div className="flex flex-col gap-1">
          <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">设备监控</h1>
          <p className="max-w-2xl text-sm text-muted-foreground sm:text-base">查看设备连接、驱动诊断和光源状态。</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => void loadStatus()} disabled={refreshing || scanning}>
            <RefreshCw data-icon="inline-start" />
            {refreshing ? '刷新中…' : '刷新状态'}
          </Button>
          <Button onClick={() => void handleScan()} disabled={refreshing || scanning}>
            <ScanSearch data-icon="inline-start" />
            {scanning ? '扫描中…' : '扫描设备'}
          </Button>
        </div>
      </div>

      {error && (
        <Alert variant="destructive">
          <TriangleAlert aria-hidden="true" />
          <AlertTitle>{status || light ? '部分设备状态不可用' : '设备状态不可用'}</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {loading ? (
        <div className="flex flex-col gap-6">
          <Skeleton className="h-[360px]" />
          <div className="grid gap-6 xl:grid-cols-2"><Skeleton className="h-80" /><Skeleton className="h-80" /></div>
        </div>
      ) : status || light ? (
        <>
          {status ? <Card>
            <CardHeader>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="flex flex-col gap-1">
                  <CardTitle>设备概览</CardTitle>
                  <CardDescription>运行配置：{status.runtime_mode}</CardDescription>
                </div>
                <Badge variant={realMode ? 'destructive' : 'secondary'}>{realMode ? '真机' : '非真机，未连接设备'}</Badge>
              </div>
            </CardHeader>
            <CardContent className="p-0">
              <DeviceRow
                icon={SlidersHorizontal}
                name="WayneLabs 位移台"
                description={stageError ?? `配置端口 ${status.scan.configured_stage_port}; 系统发现 ${status.scan.serial_ports.length} 个串口`}
                status={stageError ? '异常' : stageConnected ? '已连接' : realMode ? '未发现' : '未探测'}
                variant={stageError ? 'destructive' : stageConnected ? 'default' : 'secondary'}
              />
              <DeviceRow
                icon={Waves}
                name="Zolix 光谱仪"
                description={spectrometerConnected ? status.scan.zolix_devices.join(', ') : '通过 USB 与厂家 DLL 通信'}
                status={spectrometerConnected ? '已连接' : realMode ? '未发现' : '未探测'}
                variant={spectrometerConnected ? 'default' : 'secondary'}
              />
              <DeviceRow
                icon={Camera}
                name="DField 相机"
                description="通过厂家 DLL 通信"
                status={cameraConnected ? '可用' : realMode ? '不可用' : '未探测'}
                variant={cameraConnected ? 'default' : 'secondary'}
              />
              <DeviceRow
                icon={Lightbulb}
                name="光源控制"
                description={light?.manual_control ? '人工控制' : `控制器类型 ${light?.type ?? '未知'}`}
                status={lightDanger ? '可能开启' : laserState === 'off_confirmed' ? '激光已关闭' : light?.manual_control ? '手动控制' : '状态未知'}
                variant={lightDanger ? 'destructive' : laserState === 'off_confirmed' ? 'default' : 'outline'}
              />
            </CardContent>
          </Card> : null}

          <div className="grid gap-6 xl:grid-cols-2">
            {status ? <Card>
              <CardHeader>
                <CardTitle>驱动与端口诊断</CardTitle>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader><TableRow><TableHead>检查项</TableHead><TableHead className="text-right">结果</TableHead></TableRow></TableHeader>
                  <TableBody>
                    {Object.entries(status.doctor).map(([key, value]) => (
                      <TableRow key={key}>
                        <TableCell>{diagnosticLabels[key] ?? key}</TableCell>
                        <TableCell className="text-right"><Badge variant={typeof value === 'boolean' ? value ? 'secondary' : 'outline' : 'outline'}>{formatValue(value)}</Badge></TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card> : null}

            {light ? <Card>
              <CardHeader>
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="flex flex-col gap-1">
                    <CardTitle>光源状态</CardTitle>
                    <CardDescription>{light?.hardware_state ? '控制器寄存器读回' : '无读回'}</CardDescription>
                  </div>
                  <Button variant="destructive" size="sm" onClick={() => setShowOffDialog(true)}>
                    <Lightbulb data-icon="inline-start" />
                    全部关闭
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="flex flex-col gap-4">
                {light?.hardware_state ? (
                  <>
                    <dl className="grid gap-3 text-sm sm:grid-cols-2">
                      <div className="rounded-md border p-4"><dt className="text-muted-foreground">激光状态</dt><dd className="mt-1 font-medium">{formatValue(light.hardware_state.laser_state)}</dd></div>
                      <div className="rounded-md border p-4"><dt className="text-muted-foreground">LED 状态</dt><dd className="mt-1 font-medium">{formatValue(light.hardware_state.led_state)}</dd></div>
                      <div className="rounded-md border p-4 sm:col-span-2"><dt className="text-muted-foreground">电压寄存器</dt><dd className="mt-1 font-medium">{formatValue(light.hardware_state.voltage_register)}</dd></div>
                    </dl>
                    {light.hardware_state.channel_states && (
                      <div className="flex flex-wrap gap-2">
                        {Object.entries(light.hardware_state.channel_states).map(([channel, value]) => (
                          <Badge key={channel} variant={value === 0 ? 'secondary' : 'destructive'}>通道 {channel}: {value === 0 ? '关' : value}</Badge>
                        ))}
                      </div>
                    )}
                  </>
                ) : (
                  <Alert>
                    <Lightbulb aria-hidden="true" />
                    <AlertTitle>{light?.manual_control ? '人工控制光源' : '没有寄存器状态'}</AlertTitle>
                    <AlertDescription>{light?.manual_control ? '人工开关的光源无法读取状态，请在实验台查看。' : '控制器没有返回寄存器状态。'}</AlertDescription>
                  </Alert>
                )}
              </CardContent>
            </Card> : null}
          </div>
        </>
      ) : null}

      <AlertDialog open={showOffDialog} onOpenChange={setShowOffDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>关闭全部光源？</AlertDialogTitle>
            <AlertDialogDescription>
              有任务运行时先停止所有任务，再关闭全部通道并读回确认。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={turningOff}>取消</AlertDialogCancel>
            <AlertDialogAction variant="destructive" disabled={turningOff} onClick={(event) => {
              event.preventDefault();
              void handleLightOff();
            }}>
              {turningOff ? '正在关闭…' : '确认全部关闭'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
