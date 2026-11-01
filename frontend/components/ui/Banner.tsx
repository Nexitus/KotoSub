import React from 'react';
import { CircleAlert, TriangleAlert } from 'lucide-react';
import { Alert, AlertDescription } from '@/components/ui/alert';

type BannerVariant = 'error' | 'warning';

interface BannerProps {
  children: React.ReactNode;
  variant?: BannerVariant;
}

const Banner: React.FC<BannerProps> = ({ children, variant = 'error' }) => {
  const Icon = variant === 'error' ? CircleAlert : TriangleAlert;
  return (
    <Alert
      variant={variant === 'error' ? 'destructive' : 'default'}
      className={variant === 'warning' ? 'border-warning/30 text-warning' : undefined}
    >
      <Icon />
      <AlertDescription className={variant === 'warning' ? 'text-warning' : undefined}>
        {children}
      </AlertDescription>
    </Alert>
  );
};

export default Banner;
