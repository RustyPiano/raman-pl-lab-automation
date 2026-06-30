import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

export function TrayScanning() {
  return (
    <div className="container mx-auto py-8">
      <h1 className="text-3xl font-bold mb-6">托盘扫描</h1>
      <Card>
        <CardHeader>
          <CardTitle>功能开发中</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground">
            托盘扫描功能将在 Phase B 中实现。
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
