import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

export function History() {
  return (
    <div className="container mx-auto py-8">
      <h1 className="text-3xl font-bold mb-6">历史记录</h1>
      <Card>
        <CardHeader>
          <CardTitle>功能开发中</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground">
            历史记录功能将在 Phase B 中实现。
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
