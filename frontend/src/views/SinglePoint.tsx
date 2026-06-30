import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { SafetyConfirm } from '@/components/SafetyConfirm';
import { ProgressDisplay } from '@/components/ProgressDisplay';
import { SpectrumChart } from '@/components/SpectrumChart';
import { useWorkflowStore } from '@/stores/workflowStore';
import apiClient, { getErrorMessage } from '@/api/client';
import { toast } from 'sonner';
import { Play, Square } from 'lucide-react';

export function SinglePoint() {
  const [configs, setConfigs] = useState<string[]>([]);
  const [selectedConfig, setSelectedConfig] = useState<string>('');
  const [mode, setMode] = useState<'dry_run' | 'simulated' | 'real'>('dry_run');
  const [sampleId, setSampleId] = useState('');
  const [operator, setOperator] = useState('');
  const [subtractBackground, setSubtractBackground] = useState(true);
  const [showSafetyDialog, setShowSafetyDialog] = useState(false);
  const [isStarting, setIsStarting] = useState(false);

  const { currentJob, startSinglePoint, stopJob, clearLogs } = useWorkflowStore();

  const isRunning = currentJob?.status === 'running' || currentJob?.status === 'pending';

  // Load configs on mount
  useEffect(() => {
    loadConfigs();
  }, []);

  const loadConfigs = async () => {
    try {
      const response = await apiClient.getConfigs();
      setConfigs(response.data);
      if (response.data.length > 0 && response.data[0]) {
        setSelectedConfig(response.data[0]);
      }
    } catch (error) {
      toast.error('加载配置失败: ' + getErrorMessage(error));
    }
  };

  const handleStartClick = () => {
    if (!selectedConfig) {
      toast.error('请选择配置文件');
      return;
    }

    if (mode === 'real') {
      setShowSafetyDialog(true);
    } else {
      handleStart();
    }
  };

  const handleStart = async () => {
    setIsStarting(true);
    clearLogs();

    try {
      const overrides: any = {};
      if (sampleId) overrides.sample_id = sampleId;
      if (operator) overrides.operator = operator;
      overrides.subtract_background = subtractBackground;

      await startSinglePoint(selectedConfig, mode, overrides);
      toast.success('任务已启动');
    } catch (error) {
      toast.error('启动失败: ' + getErrorMessage(error));
    } finally {
      setIsStarting(false);
      setShowSafetyDialog(false);
    }
  };

  const handleStop = async () => {
    if (!currentJob) return;

    try {
      await stopJob(currentJob.job_id);
      toast.info('任务已停止');
    } catch (error) {
      toast.error('停止失败: ' + getErrorMessage(error));
    }
  };

  return (
    <div className="container mx-auto py-8 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">单点 Raman 测量</h1>
      </div>

      {/* Configuration Card */}
      <Card>
        <CardHeader>
          <CardTitle>测量配置</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            {/* Config selection */}
            <div className="space-y-2">
              <Label htmlFor="config">配置文件</Label>
              <Select value={selectedConfig} onValueChange={setSelectedConfig} disabled={isRunning}>
                <SelectTrigger id="config">
                  <SelectValue placeholder="选择配置..." />
                </SelectTrigger>
                <SelectContent>
                  {configs.map((config) => (
                    <SelectItem key={config} value={config}>
                      {config}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Mode selection */}
            <div className="space-y-2">
              <Label htmlFor="mode">运行模式</Label>
              <Select value={mode} onValueChange={(v: any) => setMode(v)} disabled={isRunning}>
                <SelectTrigger id="mode">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="dry_run">Dry Run (空运行)</SelectItem>
                  <SelectItem value="simulated">Simulated (模拟)</SelectItem>
                  <SelectItem value="real">Real (真机)</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* Overrides */}
          <div className="border-t pt-4 space-y-4">
            <h3 className="font-medium text-sm text-muted-foreground">参数覆盖（可选）</h3>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="sample-id">样品 ID</Label>
                <Input
                  id="sample-id"
                  placeholder="例如: sample-001"
                  value={sampleId}
                  onChange={(e) => setSampleId(e.target.value)}
                  disabled={isRunning}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="operator">操作员</Label>
                <Input
                  id="operator"
                  placeholder="例如: 张三"
                  value={operator}
                  onChange={(e) => setOperator(e.target.value)}
                  disabled={isRunning}
                />
              </div>
            </div>

            <div className="flex items-center space-x-2">
              <input
                type="checkbox"
                id="subtract-bg"
                checked={subtractBackground}
                onChange={(e) => setSubtractBackground(e.target.checked)}
                disabled={isRunning}
                className="w-4 h-4 rounded border-gray-300"
              />
              <Label htmlFor="subtract-bg" className="cursor-pointer">
                背景扣除
              </Label>
            </div>
          </div>

          {/* Action buttons */}
          <div className="flex gap-3 pt-2">
            {!isRunning ? (
              <Button
                onClick={handleStartClick}
                disabled={isStarting || !selectedConfig}
                className="bg-green-600 hover:bg-green-700 text-lg py-6 flex-1"
                size="lg"
              >
                <Play className="mr-2 h-5 w-5" />
                开始测量
              </Button>
            ) : (
              <Button
                onClick={handleStop}
                variant="destructive"
                className="text-lg py-6 flex-1"
                size="lg"
              >
                <Square className="mr-2 h-5 w-5" />
                停止测量
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Progress Display */}
      {currentJob && <ProgressDisplay />}

      {/* Result Display */}
      {currentJob?.result && <SpectrumChart result={currentJob.result} />}

      {/* Error Display */}
      {currentJob?.error && (
        <Card className="border-red-200 bg-red-50">
          <CardHeader>
            <CardTitle className="text-red-600">❌ 错误</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-red-700">{currentJob.error}</p>
          </CardContent>
        </Card>
      )}

      {/* Safety Confirmation Dialog */}
      <SafetyConfirm
        open={showSafetyDialog}
        onOpenChange={setShowSafetyDialog}
        onConfirm={handleStart}
      />
    </div>
  );
}
