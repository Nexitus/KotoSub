import React from 'react';
import { Card as UICard, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

interface CardProps {
  title?: string;
  children: React.ReactNode;
}

const Card: React.FC<CardProps> = ({ title, children }) => {
  return (
    <UICard className="gap-4 py-5">
      {title && (
        <CardHeader className="px-5">
          <CardTitle className="text-sm">{title}</CardTitle>
        </CardHeader>
      )}
      <CardContent className="px-5">{children}</CardContent>
    </UICard>
  );
};

export default Card;
