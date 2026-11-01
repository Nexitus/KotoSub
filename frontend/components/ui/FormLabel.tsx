import React from 'react';
import { Label } from '@/components/ui/label';

interface FormLabelProps {
  children: React.ReactNode;
  htmlFor?: string;
}

const FormLabel: React.FC<FormLabelProps> = ({ children, htmlFor }) => (
  <Label htmlFor={htmlFor} className="mb-2 text-xs font-medium text-muted-foreground">
    {children}
  </Label>
);

export default FormLabel;
