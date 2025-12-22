
import React from 'react';
import { ViewType } from '../types';
import { COLORS, ICONS } from '../constants';

interface HeaderProps {
  activeView: ViewType;
  onViewChange: (view: ViewType) => void;
}

const Header: React.FC<HeaderProps> = ({ activeView, onViewChange }) => {
  return (
    <header className="bg-white border-b border-gray-100 shadow-sm">
      <div className="container mx-auto px-6 py-8 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold mb-1" style={{ color: COLORS.PURPLE }}>
            KotoSub
          </h1>
          <p className="text-gray-500 font-medium">
            AI-powered Transcription and Translation tool
          </p>
        </div>

        <nav className="flex space-x-1 bg-gray-100 p-1 rounded-lg">
          <button
            onClick={() => onViewChange(ViewType.TRANSLATOR)}
            className={`flex items-center space-x-2 px-6 py-2 rounded-md font-semibold transition-all duration-200 ${activeView === ViewType.TRANSLATOR
              ? 'bg-white shadow-sm'
              : 'text-gray-500 hover:text-gray-700'
              }`}
            style={activeView === ViewType.TRANSLATOR ? { color: COLORS.PURPLE } : {}}
          >
            <ICONS.Translate />
            <span>Translator</span>
          </button>
          <button
            onClick={() => onViewChange(ViewType.SETTINGS)}
            className={`flex items-center space-x-2 px-6 py-2 rounded-md font-semibold transition-all duration-200 ${activeView === ViewType.SETTINGS
              ? 'bg-white shadow-sm'
              : 'text-gray-500 hover:text-gray-700'
              }`}
            style={activeView === ViewType.SETTINGS ? { color: COLORS.PURPLE } : {}}
          >
            <ICONS.Settings />
            <span>Settings</span>
          </button>
        </nav>
      </div>
    </header>
  );
};

export default Header;
