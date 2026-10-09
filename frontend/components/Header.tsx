import React, { useState } from 'react';
import { ViewType } from '../types';
import { ICONS } from '../constants';
import TabGroup, { TabOption } from './ui/TabGroup';

interface HeaderProps {
  activeView: ViewType;
  onViewChange: (view: ViewType) => void;
}

const NAV_OPTIONS: TabOption<ViewType>[] = [
  { value: ViewType.TRANSLATOR, label: 'Translator', icon: <ICONS.Translate /> },
  { value: ViewType.SETTINGS,   label: 'Settings',   icon: <ICONS.Settings /> },
];

const THEME_KEY = 'kotosub_theme';

const Header: React.FC<HeaderProps> = ({ activeView, onViewChange }) => {
  const [dark, setDark] = useState<boolean>(() =>
    document.documentElement.classList.contains('dark')
  );

  const toggleTheme = () => {
    const next = !dark;
    setDark(next);
    document.documentElement.classList.toggle('dark', next);
    try {
      localStorage.setItem(THEME_KEY, next ? 'dark' : 'light');
    } catch { /* private mode */ }
  };

  return (
    <header className="sticky top-0 z-30 bg-raised/85 backdrop-blur border-b border-edge">
      <div className="container mx-auto px-4 sm:px-6 py-2 flex flex-col md:flex-row md:items-center justify-between gap-2">
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-bold text-brand tracking-tight">
            KotoSub
          </h1>
          <span className="hidden lg:block text-xs text-ink-faint">
            AI subtitle translator
          </span>
        </div>
        <div className="flex items-center gap-2">
          <TabGroup options={NAV_OPTIONS} value={activeView} onChange={onViewChange} />
          <button
            onClick={toggleTheme}
            aria-label={dark ? 'Switch to light mode' : 'Switch to dark mode'}
            className="p-2.5 rounded-lg text-ink-soft hover:text-ink hover:bg-edge/60 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand"
          >
            {dark ? <ICONS.Sun /> : <ICONS.Moon />}
          </button>
        </div>
      </div>
    </header>
  );
};

export default Header;
