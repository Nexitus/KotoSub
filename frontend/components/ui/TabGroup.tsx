import React from 'react';

export interface TabOption<T extends string = string> {
  value: T;
  label: string;
  icon?: React.ReactNode;
}

interface TabGroupProps<T extends string = string> {
  options: TabOption<T>[];
  value: T;
  onChange: (value: T) => void;
}

function TabGroup<T extends string>({ options, value, onChange }: TabGroupProps<T>) {
  return (
    <nav className="flex space-x-1 bg-edge/60 p-1 rounded-lg">
      {options.map((opt) => (
        <button
          key={opt.value}
          onClick={() => onChange(opt.value)}
          aria-current={value === opt.value ? 'page' : undefined}
          className={`flex items-center space-x-2 px-5 py-2 rounded-md font-semibold text-sm transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-1 focus-visible:ring-brand ${
            value === opt.value
              ? 'bg-raised text-brand shadow-sm'
              : 'text-ink-faint hover:text-ink'
          }`}
        >
          {opt.icon}
          {opt.label && <span>{opt.label}</span>}
        </button>
      ))}
    </nav>
  );
}

export default TabGroup;
