import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { useState } from 'react';

interface SpectrumChartProps {
  result?: any;
}

export function SpectrumChart({ result }: SpectrumChartProps) {
  const [showCorrected, setShowCorrected] = useState(true);

  if (!result || !result.spectrum) {
    return null;
  }

  const { spectrum, wavelengths, metadata } = result;

  // Prepare data for recharts
  const chartData = wavelengths
    ? wavelengths.map((wl: number, idx: number) => ({
        wavelength: wl,
        raw: spectrum.raw?.[idx] || 0,
        corrected: spectrum.corrected?.[idx] || spectrum.raw?.[idx] || 0,
      }))
    : spectrum.raw?.map((value: number, idx: number) => ({
        pixel: idx,
        raw: value,
        corrected: spectrum.corrected?.[idx] || value,
      })) || [];

  const xAxisKey = wavelengths ? 'wavelength' : 'pixel';
  const xAxisLabel = wavelengths ? '波长 (nm)' : '像素索引';

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>光谱数据</CardTitle>
          <div className="flex gap-2">
            <Button
              variant={!showCorrected ? 'default' : 'outline'}
              size="sm"
              onClick={() => setShowCorrected(false)}
            >
              原始
            </Button>
            <Button
              variant={showCorrected ? 'default' : 'outline'}
              size="sm"
              onClick={() => setShowCorrected(true)}
            >
              校正
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={400}>
          <LineChart data={chartData} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis
              dataKey={xAxisKey}
              label={{ value: xAxisLabel, position: 'insideBottom', offset: -5 }}
            />
            <YAxis label={{ value: '强度', angle: -90, position: 'insideLeft' }} />
            <Tooltip />
            <Legend />
            {!showCorrected && (
              <Line
                type="monotone"
                dataKey="raw"
                stroke="#3b82f6"
                name="原始光谱"
                dot={false}
                strokeWidth={2}
              />
            )}
            {showCorrected && (
              <Line
                type="monotone"
                dataKey="corrected"
                stroke="#10b981"
                name="校正光谱"
                dot={false}
                strokeWidth={2}
              />
            )}
          </LineChart>
        </ResponsiveContainer>

        {/* Metadata */}
        {metadata && (
          <div className="mt-4 text-sm text-muted-foreground space-y-1">
            <div className="grid grid-cols-2 gap-2">
              {metadata.sample_id && (
                <div>
                  <span className="font-medium">样品ID:</span> {metadata.sample_id}
                </div>
              )}
              {metadata.operator && (
                <div>
                  <span className="font-medium">操作员:</span> {metadata.operator}
                </div>
              )}
              {metadata.timestamp && (
                <div>
                  <span className="font-medium">时间:</span>{' '}
                  {new Date(metadata.timestamp).toLocaleString('zh-CN')}
                </div>
              )}
              {metadata.integration_time && (
                <div>
                  <span className="font-medium">积分时间:</span> {metadata.integration_time}ms
                </div>
              )}
            </div>
          </div>
        )}

        {/* Warnings */}
        {result.warnings && result.warnings.length > 0 && (
          <div className="mt-4 p-3 bg-amber-50 border border-amber-200 rounded-md">
            <div className="font-medium text-amber-800 mb-1">⚠️ 警告</div>
            <ul className="text-sm text-amber-700 space-y-1 list-disc list-inside">
              {result.warnings.map((warning: string, idx: number) => (
                <li key={idx}>{warning}</li>
              ))}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
