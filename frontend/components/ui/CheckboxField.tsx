import React from 'react';

interface CheckboxFieldProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label: string;
  description?: string;
  id?: string;
}

const CheckboxField: React.FC<CheckboxFieldProps> = ({ checked, onChange, label, description, id }) => (
  <label className="flex items-start space-x-3 cursor-pointer group" htmlFor={id}>
    <input
      id={id}
      type="checkbox"
      className="w-5 h-5 mt-0.5 rounded border-edge-strong accent-brand focus:ring-brand shrink-0"
      checked={checked}
      onChange={(e) => onChange(e.target.checked)}
    />
    <div className="flex flex-col">
      <span className="font-medium text-ink">{label}</span>
      {description && (
        <span className="text-xs text-ink-faint">{description}</span>
      )}
    </div>
  </label>
);

export default CheckboxField;
