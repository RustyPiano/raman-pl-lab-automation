import { useState } from 'react';
import { TriangleAlert } from 'lucide-react';

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
import { Checkbox } from '@/components/ui/checkbox';
import { Field, FieldGroup, FieldLabel } from '@/components/ui/field';

interface SafetyConfirmProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: () => void;
}

const safetyItems = [
  ['sample', '样品已正确放置'],
  ['eyewear', '激光防护眼镜已佩戴'],
  ['area', '实验区域无无关人员'],
  ['path', '激光路径畅通无阻'],
] as const;

type SafetyCheck = (typeof safetyItems)[number][0];
const unchecked = (): Record<SafetyCheck, boolean> => ({
  sample: false,
  eyewear: false,
  area: false,
  path: false,
});

export function SafetyConfirm({ open, onOpenChange, onConfirm }: SafetyConfirmProps) {
  const [checks, setChecks] = useState(unchecked);
  const allConfirmed = Object.values(checks).every(Boolean);

  const handleOpenChange = (nextOpen: boolean) => {
    if (!nextOpen) setChecks(unchecked());
    onOpenChange(nextOpen);
  };

  const handleConfirm = () => {
    if (!allConfirmed) return;
    onConfirm();
    setChecks(unchecked());
  };

  return (
    <AlertDialog open={open} onOpenChange={handleOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle className="flex items-center gap-2 text-destructive">
            <TriangleAlert aria-hidden="true" />
            激光安全确认
          </AlertDialogTitle>
          <AlertDialogDescription>
            真机测量会开启激光，请逐项确认。
          </AlertDialogDescription>
        </AlertDialogHeader>

        <FieldGroup data-slot="checkbox-group" className="gap-3">
          {safetyItems.map(([id, label]) => (
            <Field key={id} orientation="horizontal">
              <Checkbox
                id={`safety-${id}`}
                checked={checks[id]}
                onCheckedChange={(checked) =>
                  setChecks((current) => ({ ...current, [id]: checked === true }))
                }
              />
              <FieldLabel htmlFor={`safety-${id}`} className="cursor-pointer">
                {label}
              </FieldLabel>
            </Field>
          ))}
        </FieldGroup>

        <AlertDialogFooter>
          <AlertDialogCancel>取消</AlertDialogCancel>
          <AlertDialogAction
            variant="destructive"
            disabled={!allConfirmed}
            onClick={handleConfirm}
          >
            确认开启
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
