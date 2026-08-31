import { useEffect, useMemo, useState } from 'react';
import { ClipboardList, LayoutGrid, RefreshCw, Route, ShieldAlert } from 'lucide-react';
import { toast } from 'sonner';

import apiClient, { getErrorMessage } from '@/api/client';
import type { TrayPreview } from '@/api/client';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from '@/components/ui/empty';
import { Field, FieldDescription, FieldGroup, FieldLabel } from '@/components/ui/field';
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';

const roleLabel = (role: string) => role === 'center' ? '中心点' : role.replace('surrounding_', '周边点 ');

function describeAction(action: string) {
  const [kind = '', first = '', second = ''] = action.split(':');
  switch (kind) {
    case 'move_wafer':
      return { label: `移动至托盘位 ${Number(first) + 1}`, detail: `坐标 ${second} µm`, variant: 'default' as const };
    case 'capture_wafer_image':
      return { label: '采集晶圆图像', detail: `托盘位 ${Number(first) + 1}`, variant: 'secondary' as const };
    case 'move_point':
      return { label: `移动至${roleLabel(first)}`, detail: `坐标 ${second} µm`, variant: 'outline' as const };
    case 'measure':
      return { label: `光谱采集 · ${roleLabel(first)}`, detail: `第 ${Number(second.replace('rep', '')) + 1} 次`, variant: 'secondary' as const };
    case 'burn_check':
      return { label: `烧样检查 · ${roleLabel(first)}`, detail: '比较重复光谱', variant: 'outline' as const };
    case 'return_wafer_center':
      return { label: '返回晶圆中心', detail: `托盘位 ${Number(first) + 1}`, variant: 'default' as const };
    default:
      return { label: action, detail: '', variant: 'outline' as const };
  }
}

export function TrayScanning() {
  const [configs, setConfigs] = useState<string[]>([]);
  const [selectedConfig, setSelectedConfig] = useState('');
  const [preview, setPreview] = useState<TrayPreview | null>(null);
  const [selectedWafer, setSelectedWafer] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    const load = async () => {
      try {
        const response = await apiClient.getConfigs('tray');
        if (!active) return;
        setConfigs(response.data.configs);
        const first = response.data.configs[0] ?? '';
        setSelectedConfig(first);
        if (first) {
          const previewResponse = await apiClient.previewTray(first);
          if (!active) return;
          setPreview(previewResponse.data);
          setSelectedWafer(previewResponse.data.wafers[0]?.index ?? null);
        }
      } catch (loadError) {
        if (active) setError(getErrorMessage(loadError));
      } finally {
        if (active) setLoading(false);
      }
    };
    void load();
    return () => { active = false; };
  }, []);

  const handleConfigChange = (value: string) => {
    setSelectedConfig(value);
    setPreview(null);
    setSelectedWafer(null);
    setError(null);
  };

  const handlePreview = async () => {
    if (!selectedConfig) return;
    setGenerating(true);
    setError(null);
    try {
      const response = await apiClient.previewTray(selectedConfig);
      setPreview(response.data);
      setSelectedWafer(response.data.wafers[0]?.index ?? null);
      toast.success('托盘安全预演已更新');
    } catch (previewError) {
      setError(getErrorMessage(previewError));
      toast.error(`生成预演失败：${getErrorMessage(previewError)}`);
    } finally {
      setGenerating(false);
    }
  };

  const actionRows = useMemo(() => {
    let waferIndex: number | null = null;
    return (preview?.actions ?? []).map((action, index) => {
      if (action.startsWith('move_wafer:')) waferIndex = Number(action.split(':')[1]);
      return { sequence: index + 1, waferIndex, action, ...describeAction(action) };
    });
  }, [preview]);
  const visibleActions = selectedWafer === null
    ? actionRows
    : actionRows.filter((action) => action.waferIndex === selectedWafer);

  return (
    <div className="mx-auto flex w-full max-w-[1480px] flex-col gap-6 px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div className="flex flex-col gap-1">
          <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">托盘扫描</h1>
          <p className="max-w-2xl text-sm text-muted-foreground sm:text-base">验证托盘几何、测点图案和动作顺序，不触碰任何真实硬件。</p>
        </div>
        <Badge variant="secondary" className="w-fit">仅安全预演</Badge>
      </div>

      <Alert>
        <ShieldAlert aria-hidden="true" />
        <AlertTitle>真实托盘扫描暂未开放</AlertTitle>
        <AlertDescription>
          相机到识别掩码的链路及现场标定尚未接通。当前页面只生成确定性的 dry-run 计划，不会移动位移台或开启光源。
        </AlertDescription>
      </Alert>

      <Card>
        <CardHeader>
          <CardTitle>预演配置</CardTitle>
          <CardDescription>只列出已通过完整托盘配置校验的 YAML 文件。</CardDescription>
        </CardHeader>
        <CardContent>
          <FieldGroup>
            <Field>
              <FieldLabel htmlFor="tray-config">托盘配置文件</FieldLabel>
              <Select value={selectedConfig} onValueChange={handleConfigChange} disabled={loading || generating || configs.length === 0}>
                <SelectTrigger id="tray-config"><SelectValue placeholder="选择托盘配置…" /></SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    {configs.map((config) => <SelectItem key={config} value={config}>{config}</SelectItem>)}
                  </SelectGroup>
                </SelectContent>
              </Select>
              <FieldDescription>预演使用一个固定模拟样品中心，用于检查完整动作数量和顺序。</FieldDescription>
            </Field>
          </FieldGroup>
        </CardContent>
        <CardFooter>
          <Button onClick={() => void handlePreview()} disabled={!selectedConfig || generating}>
            <RefreshCw data-icon="inline-start" />
            {generating ? '正在生成…' : '生成安全预演'}
          </Button>
        </CardFooter>
      </Card>

      {error && (
        <Alert variant="destructive">
          <ShieldAlert aria-hidden="true" />
          <AlertTitle>无法生成托盘预演</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {loading ? (
        <div className="grid gap-6 xl:grid-cols-[minmax(0,1.25fr)_minmax(320px,0.75fr)]">
          <Skeleton className="h-[420px]" />
          <Skeleton className="h-[420px]" />
        </div>
      ) : preview ? (
        <>
          <div className="grid gap-6 xl:grid-cols-[minmax(0,1.25fr)_minmax(320px,0.75fr)]">
            <Card>
              <CardHeader>
                <div className="flex items-start justify-between gap-3">
                  <div className="flex flex-col gap-1">
                    <CardTitle>托盘路径</CardTitle>
                    <CardDescription>{preview.layout.rows} 行 × {preview.layout.cols} 列 · {preview.layout.order === 'serpentine' ? '蛇形顺序' : '逐行顺序'}</CardDescription>
                  </div>
                  <Route aria-hidden="true" className="size-5 text-muted-foreground" />
                </div>
              </CardHeader>
              <CardContent>
                <div className="overflow-x-auto pb-1">
                  <div
                    className="grid gap-3"
                    style={{
                      gridTemplateColumns: `repeat(${preview.layout.cols}, minmax(72px, 1fr))`,
                      minWidth: `${preview.layout.cols * 84}px`,
                    }}
                  >
                    {[...preview.wafers].sort((a, b) => a.row - b.row || a.col - b.col).map((wafer) => (
                      <Button
                        key={wafer.index}
                        type="button"
                        variant={selectedWafer === wafer.index ? 'default' : 'outline'}
                        aria-pressed={selectedWafer === wafer.index}
                        onClick={() => setSelectedWafer(wafer.index)}
                        className="aspect-square h-auto min-h-20 flex-col"
                      >
                        <span className="text-base">{wafer.index + 1}</span>
                        <span className="font-normal opacity-80">R{wafer.row + 1} · C{wafer.col + 1}</span>
                      </Button>
                    ))}
                  </div>
                </div>
                <p className="mt-4 text-xs leading-relaxed text-muted-foreground">点击托盘位查看该位置的完整动作序列；数字表示实际访问次序。</p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>计划摘要</CardTitle>
                <CardDescription>{preview.sample_id} · 操作员 {preview.operator}</CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-5">
                <dl className="grid grid-cols-2 overflow-hidden rounded-lg border">
                  {[
                    ['托盘位', preview.summary.wafer_count],
                    ['测量点', preview.summary.measurement_points],
                    ['光谱采集', preview.summary.acquisitions],
                    ['动作总数', preview.summary.action_count],
                  ].map(([label, value]) => (
                    <div key={label} className="flex min-h-24 flex-col justify-center gap-1 border-b p-4 odd:border-r last:border-b-0 [&:nth-last-child(2)]:border-b-0">
                      <dt className="text-xs text-muted-foreground">{label}</dt>
                      <dd className="text-2xl font-semibold tabular-nums">{value}</dd>
                    </div>
                  ))}
                </dl>
                <dl className="flex flex-col gap-3 text-sm">
                  <div className="flex items-center justify-between gap-4"><dt className="text-muted-foreground">托盘间距</dt><dd>{preview.layout.pitch_x_um} × {preview.layout.pitch_y_um} µm</dd></div>
                  <div className="flex items-center justify-between gap-4"><dt className="text-muted-foreground">每点重复</dt><dd>{preview.pattern.repeats_per_point} 次</dd></div>
                  <div className="flex items-center justify-between gap-4"><dt className="text-muted-foreground">周边点</dt><dd>{preview.pattern.surrounding_count} 个</dd></div>
                  <div className="flex items-center justify-between gap-4"><dt className="text-muted-foreground">烧样检查</dt><dd>{preview.summary.burn_checks} 次</dd></div>
                </dl>
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <div className="flex items-start justify-between gap-3">
                <div className="flex flex-col gap-1">
                  <CardTitle>动作序列</CardTitle>
                  <CardDescription>托盘位 {selectedWafer === null ? '全部' : selectedWafer + 1} · {visibleActions.length} 个动作</CardDescription>
                </div>
                <ClipboardList aria-hidden="true" className="size-5 text-muted-foreground" />
              </div>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-20">序号</TableHead>
                    <TableHead>动作</TableHead>
                    <TableHead className="hidden sm:table-cell">参数</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {visibleActions.map((action) => (
                    <TableRow key={action.sequence}>
                      <TableCell className="font-mono text-xs tabular-nums">{String(action.sequence).padStart(2, '0')}</TableCell>
                      <TableCell><Badge variant={action.variant}>{action.label}</Badge></TableCell>
                      <TableCell className="hidden text-muted-foreground sm:table-cell">{action.detail}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </>
      ) : (
        <Card>
          <CardContent className="pt-6">
            <Empty>
              <EmptyHeader>
                <EmptyMedia variant="icon"><LayoutGrid /></EmptyMedia>
                <EmptyTitle>没有可用的托盘配置</EmptyTitle>
                <EmptyDescription>请先完成并校验一个托盘扫描 YAML 配置；含占位符的真机模板不会出现在这里。</EmptyDescription>
              </EmptyHeader>
            </Empty>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
