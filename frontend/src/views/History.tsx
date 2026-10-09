import { lazy, Suspense, useEffect, useMemo, useState } from 'react';
import { Activity, Database, Download, RefreshCw, Search, TriangleAlert } from 'lucide-react';

import apiClient, { getErrorMessage } from '@/api/client';
import type { ApiJobStatus, HistoryRecord, JobState, SpectrumResult } from '@/api/client';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from '@/components/ui/empty';
import { Field, FieldGroup, FieldLabel } from '@/components/ui/field';
import { Input } from '@/components/ui/input';
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

const SpectrumChart = lazy(() =>
  import('@/components/SpectrumChart').then((module) => ({ default: module.SpectrumChart })),
);

type HistorySource = 'measurement' | 'job';

interface HistoryRow {
  key: string;
  id: string;
  source: HistorySource;
  status: JobState;
  createdAt: string;
  sampleId: string | null;
  operator: string | null;
  mode: string;
  error: string | null;
  files: string[];
  result: SpectrumResult | null;
}

const statusInfo: Record<JobState, { label: string; variant: 'default' | 'secondary' | 'outline' | 'destructive' }> = {
  pending: { label: '等待中', variant: 'outline' },
  running: { label: '运行中', variant: 'default' },
  stopping: { label: '停止中', variant: 'secondary' },
  completed: { label: '已完成', variant: 'secondary' },
  failed: { label: '失败', variant: 'destructive' },
  stopped: { label: '已停止', variant: 'outline' },
};

const modeLabel = (mode: string) => ({
  dry_run: '空运行',
  simulated: '模拟',
  real: '真机',
  unknown: '未记录',
}[mode] ?? mode);

const formatDate = (value: string) => {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('zh-CN');
};

function persistedRow(record: HistoryRecord): HistoryRow {
  return {
    key: `measurement:${record.id}`,
    id: record.id,
    source: 'measurement',
    status: record.status,
    createdAt: record.created_at,
    sampleId: record.sample_id,
    operator: record.operator,
    mode: record.mode,
    error: record.error,
    files: record.files,
    result: null,
  };
}

function jobRow(job: ApiJobStatus): HistoryRow {
  return {
    key: `job:${job.id}`,
    id: job.id,
    source: 'job',
    status: job.status,
    createdAt: job.created_at,
    sampleId: job.result?.metadata.sample_id ?? null,
    operator: job.result?.metadata.operator ?? null,
    mode: job.mode ?? job.result?.mode ?? 'unknown',
    error: job.error ?? null,
    files: [],
    result: job.result ?? null,
  };
}

export function History() {
  const [rows, setRows] = useState<HistoryRow[]>([]);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [detail, setDetail] = useState<SpectrumResult | null>(null);
  const [query, setQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<'all' | JobState>('all');
  const [modeFilter, setModeFilter] = useState('all');
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);

  const loadHistory = async (quiet = false) => {
    if (!quiet) setRefreshing(true);
    setError(null);
    try {
      const [historyResponse, jobsResponse] = await Promise.all([
        apiClient.getHistory(),
        apiClient.getJobs(),
      ]);
      const persistedIds = new Set(historyResponse.data.map((record) => record.id));
      const jobs = jobsResponse.data.filter((job) => {
        const directory = job.result?.output_directory;
        const runId = directory?.split(/[\\/]/).pop();
        return !runId || !persistedIds.has(runId);
      });
      const nextRows = [
        ...historyResponse.data.map(persistedRow),
        ...jobs.map(jobRow),
      ].sort((a, b) => Date.parse(b.createdAt) - Date.parse(a.createdAt));
      setRows(nextRows);
      setSelectedKey((current) => current && nextRows.some((row) => row.key === current) ? current : nextRows[0]?.key ?? null);
    } catch (loadError) {
      setError(getErrorMessage(loadError));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    void loadHistory(true);
  }, []);

  const selected = rows.find((row) => row.key === selectedKey) ?? null;

  useEffect(() => {
    let active = true;
    setDetailError(null);
    setDetailLoading(false);
    if (!selected) {
      setDetail(null);
      return () => { active = false; };
    }
    if (selected.source === 'job') {
      setDetail(selected.result);
      return () => { active = false; };
    }
    setDetail(null);
    setDetailLoading(true);
    apiClient.getHistoryDetail(selected.id)
      .then((response) => { if (active) setDetail(response.data.result); })
      .catch((detailLoadError) => { if (active) setDetailError(getErrorMessage(detailLoadError)); })
      .finally(() => { if (active) setDetailLoading(false); });
    return () => { active = false; };
  }, [selected]);

  const filteredRows = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase('zh-CN');
    return rows.filter((row) => {
      const matchesQuery = !normalized || [row.id, row.sampleId, row.operator]
        .some((value) => value?.toLocaleLowerCase('zh-CN').includes(normalized));
      return matchesQuery
        && (statusFilter === 'all' || row.status === statusFilter)
        && (modeFilter === 'all' || row.mode === modeFilter);
    });
  }, [modeFilter, query, rows, statusFilter]);

  useEffect(() => {
    if (!filteredRows.some((row) => row.key === selectedKey)) {
      setSelectedKey(filteredRows[0]?.key ?? null);
    }
  }, [filteredRows, selectedKey]);

  return (
    <div className="mx-auto flex w-full max-w-[1600px] flex-col gap-6 px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div className="flex flex-col gap-1">
          <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">历史记录</h1>
          <p className="max-w-2xl text-sm text-muted-foreground sm:text-base">查看测量结果和失败记录，下载输出文件。</p>
        </div>
        <Button variant="outline" onClick={() => void loadHistory()} disabled={refreshing}>
          <RefreshCw data-icon="inline-start" />
          {refreshing ? '刷新中…' : '刷新记录'}
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>筛选</CardTitle>
          <CardDescription>搜索样品、操作员或记录 ID。</CardDescription>
        </CardHeader>
        <CardContent>
          <FieldGroup>
            <div className="grid gap-4 md:grid-cols-[minmax(220px,1fr)_180px_180px]">
              <Field>
                <FieldLabel htmlFor="history-search">搜索</FieldLabel>
                <div className="relative">
                  <Search aria-hidden="true" className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                  <Input id="history-search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="样品、操作员或记录 ID" className="pl-9" />
                </div>
              </Field>
              <Field>
                <FieldLabel htmlFor="history-status">状态</FieldLabel>
                <Select value={statusFilter} onValueChange={(value) => setStatusFilter(value as 'all' | JobState)}>
                  <SelectTrigger id="history-status"><SelectValue /></SelectTrigger>
                  <SelectContent><SelectGroup>
                    <SelectItem value="all">全部状态</SelectItem>
                    {Object.entries(statusInfo).map(([value, info]) => <SelectItem key={value} value={value}>{info.label}</SelectItem>)}
                  </SelectGroup></SelectContent>
                </Select>
              </Field>
              <Field>
                <FieldLabel htmlFor="history-mode">模式</FieldLabel>
                <Select value={modeFilter} onValueChange={setModeFilter}>
                  <SelectTrigger id="history-mode"><SelectValue /></SelectTrigger>
                  <SelectContent><SelectGroup>
                    <SelectItem value="all">全部模式</SelectItem>
                    <SelectItem value="dry_run">空运行</SelectItem>
                    <SelectItem value="simulated">模拟</SelectItem>
                    <SelectItem value="real">真机</SelectItem>
                    <SelectItem value="unknown">未记录</SelectItem>
                  </SelectGroup></SelectContent>
                </Select>
              </Field>
            </div>
          </FieldGroup>
        </CardContent>
      </Card>

      {error && (
        <Alert variant="destructive">
          <TriangleAlert aria-hidden="true" />
          <AlertTitle>历史记录加载失败</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {loading ? (
        <div className="grid gap-6 xl:grid-cols-[minmax(0,1.45fr)_minmax(340px,0.75fr)]"><Skeleton className="h-[560px]" /><Skeleton className="h-[560px]" /></div>
      ) : (
        <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,1.45fr)_minmax(340px,0.75fr)]">
          <Card>
            <CardHeader>
              <div className="flex items-start justify-between gap-3">
                <div className="flex flex-col gap-1"><CardTitle>任务与测量</CardTitle><CardDescription>{filteredRows.length} 条记录</CardDescription></div>
                <Database aria-hidden="true" className="size-5 text-muted-foreground" />
              </div>
            </CardHeader>
            <CardContent>
              {filteredRows.length > 0 ? (
                <Table>
                  <TableHeader><TableRow><TableHead>样品 / 记录</TableHead><TableHead>状态</TableHead><TableHead className="hidden md:table-cell">模式</TableHead><TableHead className="hidden lg:table-cell">时间</TableHead></TableRow></TableHeader>
                  <TableBody>
                    {filteredRows.map((row) => (
                      <TableRow key={row.key} data-state={row.key === selectedKey ? 'selected' : undefined}>
                        <TableCell>
                          <Button variant="link" className="h-auto max-w-64 justify-start p-0 text-left" onClick={() => setSelectedKey(row.key)}>
                            <span className="truncate">{row.sampleId ?? row.id}</span>
                          </Button>
                          <p className="mt-1 max-w-64 truncate font-mono text-xs text-muted-foreground">{row.id}</p>
                        </TableCell>
                        <TableCell><Badge variant={statusInfo[row.status].variant}>{statusInfo[row.status].label}</Badge></TableCell>
                        <TableCell className="hidden md:table-cell">{modeLabel(row.mode)}</TableCell>
                        <TableCell className="hidden whitespace-nowrap text-muted-foreground lg:table-cell">{formatDate(row.createdAt)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              ) : (
                <Empty>
                  <EmptyHeader>
                    <EmptyMedia variant="icon"><Database /></EmptyMedia>
                    <EmptyTitle>没有匹配的记录</EmptyTitle>
                    <EmptyDescription>{rows.length === 0 ? '完成一次测量后，结果会在这里出现。' : '请调整搜索词或筛选条件。'}</EmptyDescription>
                  </EmptyHeader>
                </Empty>
              )}
            </CardContent>
          </Card>

          <div className="flex min-w-0 flex-col gap-6">
            <Card>
              <CardHeader>
                <CardTitle>记录详情</CardTitle>
                <CardDescription>{selected ? selected.id : '选择一条记录查看详情'}</CardDescription>
              </CardHeader>
              <CardContent>
                {selected ? (
                  <div className="flex flex-col gap-5">
                    <dl className="flex flex-col gap-3 text-sm">
                      <div className="flex justify-between gap-4"><dt className="text-muted-foreground">样品</dt><dd className="text-right">{selected.sampleId ?? '未记录'}</dd></div>
                      <div className="flex justify-between gap-4"><dt className="text-muted-foreground">操作员</dt><dd className="text-right">{selected.operator ?? '未记录'}</dd></div>
                      <div className="flex justify-between gap-4"><dt className="text-muted-foreground">模式</dt><dd>{modeLabel(selected.mode)}</dd></div>
                      <div className="flex justify-between gap-4"><dt className="text-muted-foreground">状态</dt><dd><Badge variant={statusInfo[selected.status].variant}>{statusInfo[selected.status].label}</Badge></dd></div>
                      <div className="flex justify-between gap-4"><dt className="text-muted-foreground">时间</dt><dd className="text-right">{formatDate(selected.createdAt)}</dd></div>
                    </dl>
                    {selected.error && <Alert variant="destructive"><TriangleAlert aria-hidden="true" /><AlertTitle>任务错误</AlertTitle><AlertDescription>{selected.error}</AlertDescription></Alert>}
                    {selected.files.length > 0 && (
                      <div className="flex flex-col gap-3">
                        <p className="text-sm font-medium">输出文件</p>
                        <div className="flex flex-wrap gap-2">
                          {selected.files.map((filename) => (
                            <Button key={filename} variant="outline" size="sm" asChild>
                              <a href={apiClient.historyFileUrl(selected.id, filename)} download>
                                <Download data-icon="inline-start" />
                                {filename}
                              </a>
                            </Button>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  <Empty><EmptyHeader><EmptyMedia variant="icon"><Activity /></EmptyMedia><EmptyTitle>尚未选择记录</EmptyTitle></EmptyHeader></Empty>
                )}
              </CardContent>
            </Card>

            {detailError && <Alert variant="destructive"><TriangleAlert aria-hidden="true" /><AlertTitle>光谱读取失败</AlertTitle><AlertDescription>{detailError}</AlertDescription></Alert>}
            {detailLoading ? <Skeleton className="h-[460px]" /> : detail?.spectrum.raw.length ? (
              <Suspense fallback={<Skeleton className="h-[460px]" />}><SpectrumChart result={detail} /></Suspense>
            ) : selected ? (
              <Card><CardContent className="pt-6"><Empty><EmptyHeader><EmptyMedia variant="icon"><Activity /></EmptyMedia><EmptyTitle>暂无光谱结果</EmptyTitle><EmptyDescription>任务完成并写入结果后可查看光谱。</EmptyDescription></EmptyHeader></Empty></CardContent></Card>
            ) : null}
          </div>
        </div>
      )}
    </div>
  );
}
