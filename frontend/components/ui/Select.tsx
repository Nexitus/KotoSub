import React from 'react';

interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {}

const Select: React.FC<SelectProps> = ({ className = '', children, ...props }) => (
  <select
    className={`w-full bg-raised border border-edge rounded-lg px-4 py-3 text-ink focus:outline-none focus:ring-2 focus:ring-brand focus:border-transparent transition-all ${className}`}
    {...props}
  >
    {children}
  </select>
);

export default Select;
