import { useState } from 'react';
import { TriangleAlert } from 'lucide-react';
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import type { SpectrumResult } from '@/api/client';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group';

// 刻度最多保留一位小数，避免 589.815 这类长数字挤在一起
const formatTick = (value: number) => String(Math.round(value * 10) / 10);

interface SpectrumChartProps {
  result: SpectrumResult;
}

export function SpectrumChart({ result }: SpectrumChartProps) {
  const [series, setSeries] = useState<'raw' | 'corrected'>('corrected');
  const correctedAvailable = result.spectrum.corrected !== null;
  const activeSeries = series === 'corrected' && correctedAvailable ? 'corrected' : 'raw';
  const values = activeSeries === 'corrected' ? result.spectrum.corrected! : result.spectrum.raw;
  const xValues = result.x.length === values.length ? result.x : values.map((_, index) => index);
  const chartData = xValues.map((x, index) => ({ x, intensity: values[index] ?? 0 }));
  const wavelengthAxis = result.x_axis_type === 'wavelength_nm';
  const outputLabel = result.output_directory.split(/[\\/]/).pop() ?? result.output_directory;

  return (
    <Card>
      <CardHeader className="flex-row items-start justify-between gap-3">
        <div className="flex min-w-0 flex-1 flex-col gap-1">
          <CardTitle>光谱数据</CardTitle>
          <CardDescription className="truncate">{outputLabel}</CardDescription>
        </div>
        {correctedAvailable && (
          <ToggleGroup
            type="single"
            variant="outline"
            size="sm"
            className="shrink-0"
            value={activeSeries}
            onValueChange={(value) => {
              if (value === 'raw' || value === 'corrected') setSeries(value);
            }}
            aria-label="选择光谱序列"
          >
            <ToggleGroupItem value="raw" className="whitespace-nowrap">原始</ToggleGroupItem>
            <ToggleGroupItem value="corrected" className="whitespace-nowrap">扣除背景</ToggleGroupItem>
          </ToggleGroup>
        )}
      </CardHeader>
      <CardContent>
        <div className="h-[300px] w-full sm:h-[420px]" role="img" aria-label="光谱折线图">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 8, right: 16, left: 8, bottom: 24 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis
                dataKey="x"
                type="number"
                domain={['dataMin', 'dataMax']}
                tickFormatter={formatTick}
                minTickGap={24}
                label={{
                  value: wavelengthAxis ? '波长 (nm)' : '像素索引',
                  position: 'insideBottom',
                  offset: -16,
                }}
              />
              <YAxis tickFormatter={formatTick} width={56} label={{ value: '强度', angle: -90, position: 'insideLeft' }} />
              <Tooltip labelFormatter={(value) => `${wavelengthAxis ? '波长' : '像素'} ${value}`} />
              <Line
                type="monotone"
                dataKey="intensity"
                stroke={activeSeries === 'corrected' ? 'hsl(var(--primary))' : 'hsl(var(--foreground))'}
                name="强度"
                isAnimationActive={false}
                dot={false}
                strokeWidth={2}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>

        <dl className="mt-4 grid gap-2 text-sm text-muted-foreground sm:grid-cols-2">
          {result.metadata.sample_id && (
            <div><dt className="inline font-medium">样品 ID：</dt><dd className="inline">{result.metadata.sample_id}</dd></div>
          )}
          {result.metadata.operator && (
            <div><dt className="inline font-medium">操作员：</dt><dd className="inline">{result.metadata.operator}</dd></div>
          )}
          {result.metadata.timestamp && (
            <div><dt className="inline font-medium">时间：</dt><dd className="inline">{new Date(result.metadata.timestamp).toLocaleString('zh-CN')}</dd></div>
          )}
          {result.metadata.camera?.exposure_ms !== undefined && (
            <div><dt className="inline font-medium">曝光时间：</dt><dd className="inline">{result.metadata.camera.exposure_ms} ms</dd></div>
          )}
        </dl>

        {result.warnings.length > 0 && (
          <Alert className="mt-4">
            <TriangleAlert aria-hidden="true" />
            <AlertTitle>采集警告</AlertTitle>
            <AlertDescription>
              <ul className="flex list-inside list-disc flex-col gap-1">
              {result.warnings.map((warning, index) => (
                <li key={`${warning}-${index}`}>{warning}</li>
              ))}
              </ul>
            </AlertDescription>
          </Alert>
        )}
      </CardContent>
    </Card>
  );
}
