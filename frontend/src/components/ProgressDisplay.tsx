import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { useWorkflowStore } from '@/stores/workflowStore';

export function ProgressDisplay() {
  const currentJob = useWorkflowStore((state) => state.currentJob);
  const logs = useWorkflowStore((state) => state.logs);

  if (!currentJob) {
    return null;
  }

  const { progress, current_step, status } = currentJob;
  const stepLabel = current_step ? ({
    initializing: '初始化',
    executing: '执行测量',
    saving: '保存结果',
    completed: '已完成',
  }[current_step] ?? current_step) : '初始化…';

  const statusConfig = {
    pending: { label: '等待中', variant: 'outline' },
    running: { label: '运行中', variant: 'default' },
    stopping: { label: '安全停止中', variant: 'secondary' },
    completed: { label: '已完成', variant: 'secondary' },
    failed: { label: '失败', variant: 'destructive' },
    stopped: { label: '已停止', variant: 'outline' },
  }[status] as { label: string; variant: 'default' | 'secondary' | 'outline' | 'destructive' };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between gap-3">
          <CardTitle>任务进度</CardTitle>
          <Badge variant={statusConfig.variant}>{statusConfig.label}</Badge>
        </div>
        <CardDescription className="truncate">任务 {currentJob.id}</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="flex flex-col gap-2">
          <div className="flex justify-between text-sm">
            <span className="font-medium">{Math.round(progress)}%</span>
            <span className="text-muted-foreground">{stepLabel}</span>
          </div>
          <Progress value={progress} className="h-3" />
        </div>

        <div className="h-64 overflow-y-auto rounded-md bg-foreground p-4 font-mono text-xs text-background">
          {logs.length === 0 ? (
            <div className="mt-24 text-center text-background/60">等待日志…</div>
          ) : (
            <div className="flex flex-col gap-1">
              {logs.map((log, index) => (
                <div key={index} className="whitespace-pre-wrap">
                  {log}
                </div>
              ))}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
