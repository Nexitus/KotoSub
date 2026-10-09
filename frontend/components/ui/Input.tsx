import React from 'react';

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {}

const Input: React.FC<InputProps> = ({ className = '', ...props }) => (
  <input
    className={`w-full bg-raised border border-edge rounded-lg px-4 py-3 text-ink placeholder-ink-faint focus:outline-none focus:ring-2 focus:ring-brand focus:border-transparent transition-all ${className}`}
    {...props}
  />
);

export default Input;
