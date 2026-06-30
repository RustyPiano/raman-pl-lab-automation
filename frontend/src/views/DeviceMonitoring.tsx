import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

export function DeviceMonitoring() {
  return (
    <div className="container mx-auto py-8">
      <h1 className="text-3xl font-bold mb-6">设备监控</h1>
      <Card>
        <CardHeader>
          <CardTitle>功能开发中</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground">
            设备监控功能将在 Phase B 中实现。
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
