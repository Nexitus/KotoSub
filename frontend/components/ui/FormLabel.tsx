import React from 'react';

interface FormLabelProps {
  children: React.ReactNode;
  htmlFor?: string;
}

const FormLabel: React.FC<FormLabelProps> = ({ children, htmlFor }) => (
  <label
    htmlFor={htmlFor}
    className="block text-xs font-bold uppercase tracking-wider text-ink-faint mb-2"
  >
    {children}
  </label>
);

export default FormLabel;
