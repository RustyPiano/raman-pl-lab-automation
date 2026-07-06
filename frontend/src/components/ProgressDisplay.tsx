import { Progress } from '@/components/ui/progress';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { useWorkflowStore } from '@/stores/workflowStore';

export function ProgressDisplay() {
  const { currentJob, logs } = useWorkflowStore();

  if (!currentJob) {
    return null;
  }

  const { progress, current_step, status } = currentJob;

  const statusColor = {
    pending: 'text-gray-500',
    running: 'text-blue-600',
    stopping: 'text-amber-600',
    completed: 'text-green-600',
    failed: 'text-red-600',
    stopped: 'text-amber-600',
  }[status] || 'text-gray-500';

  const statusEmoji = {
    pending: '⏳',
    running: '▶️',
    stopping: '🟡',
    completed: '✅',
    failed: '❌',
    stopped: '⏹️',
  }[status] || '⏸️';

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <span className={statusColor}>{statusEmoji}</span>
          <span>任务进度</span>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Progress bar */}
        <div className="space-y-2">
          <div className="flex justify-between text-sm">
            <span className="font-medium">{Math.round(progress)}%</span>
            <span className="text-muted-foreground">{current_step || '初始化...'}</span>
          </div>
          <Progress value={progress} className="h-3" />
        </div>

        {/* Log window */}
        <div className="bg-slate-950 text-slate-50 rounded-md p-4 font-mono text-xs h-64 overflow-y-auto">
          {logs.length === 0 ? (
            <div className="text-slate-400 text-center mt-24">等待日志...</div>
          ) : (
            <div className="space-y-1">
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
