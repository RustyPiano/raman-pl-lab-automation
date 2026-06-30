import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';

interface SafetyConfirmProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: () => void;
}

export function SafetyConfirm({ open, onOpenChange, onConfirm }: SafetyConfirmProps) {
  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle className="flex items-center gap-2 text-amber-600">
            <span className="text-2xl">⚠️</span>
            激光安全确认
          </AlertDialogTitle>
          <AlertDialogDescription className="text-left space-y-3 pt-2">
            <p className="text-base">即将开启激光，请确认以下事项：</p>
            <div className="space-y-2 pl-2">
              <div className="flex items-start gap-2">
                <span>☐</span>
                <span>样品已正确放置</span>
              </div>
              <div className="flex items-start gap-2">
                <span>☐</span>
                <span>激光防护眼镜已佩戴</span>
              </div>
              <div className="flex items-start gap-2">
                <span>☐</span>
                <span>实验区域无无关人员</span>
              </div>
              <div className="flex items-start gap-2">
                <span>☐</span>
                <span>激光路径畅通无阻</span>
              </div>
            </div>
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>取消</AlertDialogCancel>
          <AlertDialogAction
            onClick={onConfirm}
            className="bg-red-600 hover:bg-red-700 focus:ring-red-600"
          >
            确认开启
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
