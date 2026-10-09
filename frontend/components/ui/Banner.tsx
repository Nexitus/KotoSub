import React from 'react';

type BannerVariant = 'error' | 'info' | 'success' | 'warning';

interface BannerProps {
  children: React.ReactNode;
  variant?: BannerVariant;
}

const variantClasses: Record<BannerVariant, string> = {
  error: 'bg-error/10 border-error/30 text-error',
  info: 'bg-info/10 border-info/30 text-info',
  success: 'bg-success/10 border-success/30 text-success',
  warning: 'bg-warning/10 border-warning/30 text-warning',
};

const Banner: React.FC<BannerProps> = ({ children, variant = 'error' }) => (
  <div className={`p-4 border rounded-xl text-sm font-medium ${variantClasses[variant]}`}>
    {children}
  </div>
);

export default Banner;
