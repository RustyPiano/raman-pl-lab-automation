import { lazy, Suspense, useEffect, useState } from 'react';
import { CircleAlert, Play, Square } from 'lucide-react';
import { toast } from 'sonner';

import apiClient, { getErrorMessage } from '@/api/client';
import type { RunMode } from '@/api/client';
import { ProgressDisplay } from '@/components/ProgressDisplay';
import { SafetyConfirm } from '@/components/SafetyConfirm';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Field, FieldDescription, FieldGroup, FieldLabel, FieldSeparator } from '@/components/ui/field';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useWorkflowStore } from '@/stores/workflowStore';
import { cn } from '@/lib/utils';

const SpectrumChart = lazy(() =>
  import('@/components/SpectrumChart').then((module) => ({ default: module.SpectrumChart })),
);

export function SinglePoint() {
  const [configs, setConfigs] = useState<string[]>([]);
  const [selectedConfig, setSelectedConfig] = useState('');
  const [mode, setMode] = useState<RunMode>('dry_run');
  const [sampleId, setSampleId] = useState('');
  const [operator, setOperator] = useState('');
  const [subtractBackground, setSubtractBackground] = useState<'config' | 'on' | 'off'>('config');
  const [showSafetyDialog, setShowSafetyDialog] = useState(false);
  const [isStarting, setIsStarting] = useState(false);

  const currentJob = useWorkflowStore((state) => state.currentJob);
  const startSinglePoint = useWorkflowStore((state) => state.startSinglePoint);
  const stopJob = useWorkflowStore((state) => state.stopJob);
  const clearLogs = useWorkflowStore((state) => state.clearLogs);
  const isRunning = currentJob?.status === 'running' || currentJob?.status === 'pending' || currentJob?.status === 'stopping';
  const isStopping = currentJob?.status === 'stopping';

  useEffect(() => {
    const loadConfigs = async () => {
      try {
        const response = await apiClient.getConfigs();
        setConfigs(response.data.configs);
        setSelectedConfig((current) => current || response.data.configs[0] || '');
      } catch (error) {
        toast.error(`加载配置失败: ${getErrorMessage(error)}`);
      }
    };
    void loadConfigs();
  }, []);

  const handleStartClick = () => {
    if (!selectedConfig) {
      toast.error('请选择配置文件');
      return;
    }
    if (mode === 'real') setShowSafetyDialog(true);
    else void handleStart();
  };

  const handleStart = async (confirmReal = false) => {
    setIsStarting(true);
    clearLogs();
    try {
      await startSinglePoint(selectedConfig, mode, confirmReal, {
        sample_id: sampleId.trim() || undefined,
        operator: operator.trim() || undefined,
        subtract_background:
          subtractBackground === 'config' ? undefined : subtractBackground === 'on',
      });
      toast.success('任务已启动');
    } catch (error) {
      toast.error(`启动失败: ${getErrorMessage(error)}`);
    } finally {
      setIsStarting(false);
      setShowSafetyDialog(false);
    }
  };

  const handleStop = async () => {
    if (!currentJob) return;
    try {
      await stopJob(currentJob.id);
      toast.info('停止请求已发送');
    } catch (error) {
      toast.error(`停止失败: ${getErrorMessage(error)}`);
    }
  };

  return (
    <div className="mx-auto flex w-full max-w-[1480px] flex-col gap-6 px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div className="flex flex-col gap-1">
          <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">单点 Raman 测量</h1>
          <p className="max-w-2xl text-sm text-muted-foreground sm:text-base">选择实验配置并执行一次可追踪的 Raman/PL 光谱采集。</p>
        </div>
        <Badge variant={mode === 'real' ? 'destructive' : 'secondary'} className="w-fit">
          {mode === 'dry_run' ? '安全空运行' : mode === 'simulated' ? '模拟设备' : '真机模式'}
        </Badge>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>测量配置</CardTitle>
          <CardDescription>默认不会接触真实硬件；真机模式必须完成逐项安全确认。</CardDescription>
        </CardHeader>
        <CardContent>
          <FieldGroup className="gap-5">
            <div className="grid gap-4 md:grid-cols-2">
              <Field>
                <FieldLabel htmlFor="config">配置文件</FieldLabel>
                <Select value={selectedConfig} onValueChange={setSelectedConfig} disabled={isRunning}>
                  <SelectTrigger id="config"><SelectValue placeholder="选择配置..." /></SelectTrigger>
                  <SelectContent>
                    <SelectGroup>
                      {configs.map((config) => <SelectItem key={config} value={config}>{config}</SelectItem>)}
                    </SelectGroup>
                  </SelectContent>
                </Select>
              </Field>

              <Field>
                <FieldLabel htmlFor="mode">运行模式</FieldLabel>
                <Select value={mode} onValueChange={(value) => setMode(value as RunMode)} disabled={isRunning}>
                  <SelectTrigger id="mode"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectGroup>
                      <SelectItem value="dry_run">Dry Run（空运行）</SelectItem>
                      <SelectItem value="simulated">Simulated（模拟）</SelectItem>
                      <SelectItem value="real">Real（真机）</SelectItem>
                    </SelectGroup>
                  </SelectContent>
                </Select>
                <FieldDescription>
                  {mode === 'real' ? '会打开真实设备并可能开启激光。' : '不会控制实验室真实设备。'}
                </FieldDescription>
              </Field>
            </div>

            <FieldSeparator>参数覆盖（可选）</FieldSeparator>

            <div className="grid gap-4 md:grid-cols-2">
              <Field>
                <FieldLabel htmlFor="sample-id">样品 ID</FieldLabel>
                <Input id="sample-id" placeholder="例如：sample-001" value={sampleId} onChange={(event) => setSampleId(event.target.value)} disabled={isRunning} />
              </Field>
              <Field>
                <FieldLabel htmlFor="operator">操作员</FieldLabel>
                <Input id="operator" placeholder="例如：张三" value={operator} onChange={(event) => setOperator(event.target.value)} disabled={isRunning} />
              </Field>
            </div>

            <Field>
              <FieldLabel htmlFor="subtract-bg">背景扣除</FieldLabel>
              <Select value={subtractBackground} onValueChange={(value) => setSubtractBackground(value as 'config' | 'on' | 'off')} disabled={isRunning}>
                <SelectTrigger id="subtract-bg"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    <SelectItem value="config">使用配置文件设置</SelectItem>
                    <SelectItem value="on">启用</SelectItem>
                    <SelectItem value="off">关闭</SelectItem>
                  </SelectGroup>
                </SelectContent>
              </Select>
            </Field>

          </FieldGroup>
        </CardContent>
        <CardFooter>
          {!isRunning ? (
            <Button onClick={handleStartClick} disabled={isStarting || !selectedConfig} size="lg" className="w-full sm:w-auto sm:min-w-44">
              <Play data-icon="inline-start" />
              {isStarting ? '正在启动…' : '开始测量'}
            </Button>
          ) : (
            <Button onClick={() => void handleStop()} disabled={isStopping} variant="destructive" size="lg" className="w-full sm:w-auto">
              <Square data-icon="inline-start" />
              {isStopping ? '正在等待安全停止…' : '停止测量'}
            </Button>
          )}
        </CardFooter>
      </Card>

      {currentJob && (
        <div className={cn(currentJob.result && 'grid items-start gap-6 xl:grid-cols-[320px_minmax(0,1fr)]')}>
          <ProgressDisplay />
          {currentJob.result && (
            <Suspense fallback={<p className="text-sm text-muted-foreground">正在加载光谱图…</p>}>
              <SpectrumChart result={currentJob.result} />
            </Suspense>
          )}
        </div>
      )}

      {currentJob?.error && (
        <Alert variant="destructive">
          <CircleAlert aria-hidden="true" />
          <AlertTitle>任务失败</AlertTitle>
          <AlertDescription>{currentJob.error}</AlertDescription>
        </Alert>
      )}

      <SafetyConfirm open={showSafetyDialog} onOpenChange={setShowSafetyDialog} onConfirm={() => void handleStart(true)} />
    </div>
  );
}
