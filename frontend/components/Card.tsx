import React from 'react';

interface CardProps {
  title?: string;
  children: React.ReactNode;
}

const Card: React.FC<CardProps> = ({ title, children }) => {
  return (
    <div className="bg-raised border border-edge rounded-2xl shadow-sm overflow-hidden">
      {title && (
        <div className="px-6 pt-5 pb-1">
          <p className="text-xs font-bold uppercase tracking-widest text-ink-faint">{title}</p>
        </div>
      )}
      <div className={title ? 'px-6 pt-3 pb-6' : 'p-6'}>
        {children}
      </div>
    </div>
  );
};

export default Card;
