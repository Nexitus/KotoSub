import React from 'react';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';

interface CheckboxFieldProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label: string;
  description?: string;
  id: string;
}

const CheckboxField: React.FC<CheckboxFieldProps> = ({ checked, onChange, label, description, id }) => (
  <div className="flex items-start gap-3">
    <Checkbox
      id={id}
      checked={checked}
      onCheckedChange={(v) => onChange(v === true)}
      className="mt-0.5"
    />
    <div className="grid gap-1">
      <Label htmlFor={id} className="font-medium text-foreground">
        {label}
      </Label>
      {description && <p className="text-xs text-muted-foreground">{description}</p>}
    </div>
  </div>
);

export default CheckboxField;
