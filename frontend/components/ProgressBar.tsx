
import React from 'react';
import { COLORS } from '../constants';

interface ProgressBarProps {
  progress: number;
  status: 'idle' | 'processing' | 'completed' | 'error';
}

const ProgressBar: React.FC<ProgressBarProps> = ({ progress, status }) => {
  const getFillColor = () => {
    switch (status) {
      case 'completed': return COLORS.GREEN;
      case 'error': return '#D32F2F';
      case 'processing': return COLORS.PURPLE;
      default: return '#E0E0E0';
    }
  };

  return (
    <div className="w-full bg-gray-100 h-3 rounded-full overflow-hidden border border-gray-200">
      <div 
        className="h-full transition-all duration-500 ease-out"
        style={{ 
          width: `${progress}%`, 
          backgroundColor: getFillColor() 
        }}
      />
    </div>
  );
};

export default ProgressBar;
