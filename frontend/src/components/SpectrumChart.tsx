import { useState } from 'react';
import { TriangleAlert } from 'lucide-react';
import {
  CartesianGrid,
  Legend,
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
      <CardHeader className="flex-row items-center justify-between">
        <div className="flex min-w-0 flex-col gap-1">
          <CardTitle>光谱数据</CardTitle>
          <CardDescription className="truncate">{outputLabel}</CardDescription>
        </div>
        <ToggleGroup
          type="single"
          variant="outline"
          size="sm"
          value={activeSeries}
          onValueChange={(value) => {
            if (value === 'raw' || value === 'corrected') setSeries(value);
          }}
          aria-label="选择光谱序列"
        >
          <ToggleGroupItem value="raw" aria-label="显示原始光谱">原始</ToggleGroupItem>
          {correctedAvailable && (
            <ToggleGroupItem value="corrected" aria-label="显示校正光谱">校正</ToggleGroupItem>
          )}
        </ToggleGroup>
      </CardHeader>
      <CardContent>
        <div className="h-[300px] w-full sm:h-[420px]" role="img" aria-label="光谱折线图">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 5, right: 30, left: 20, bottom: 20 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis
                dataKey="x"
                label={{
                  value: wavelengthAxis ? '波长 (nm)' : '像素索引',
                  position: 'insideBottom',
                  offset: -12,
                }}
              />
              <YAxis label={{ value: '强度', angle: -90, position: 'insideLeft' }} />
              <Tooltip />
              <Legend />
              <Line
                type="monotone"
                dataKey="intensity"
                stroke={activeSeries === 'corrected' ? 'hsl(var(--primary))' : 'hsl(var(--foreground))'}
                name={activeSeries === 'corrected' ? '校正光谱' : '原始光谱'}
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
