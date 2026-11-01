import React, { useState } from 'react';
import { Languages, Settings } from 'lucide-react';
import { ViewType } from '../types';
import { TabsList, TabsTrigger } from '@/components/ui/tabs';
import SwitchButton from '@/components/kokonutui/switch-button';

const THEME_KEY = 'kotosub_theme';

// Active pill = brand purple, the same active treatment as checkbox/slider.
const NAV_TRIGGER_CLASS =
  'rounded-full px-3.5 py-1.5 text-zinc-500 dark:text-zinc-400 data-[state=active]:bg-white data-[state=active]:text-brand data-[state=active]:shadow-xs dark:data-[state=active]:border-transparent dark:data-[state=active]:bg-zinc-800 dark:data-[state=active]:text-brand';

const Header: React.FC = () => {
  const [dark, setDark] = useState<boolean>(() =>
    document.documentElement.classList.contains('dark')
  );

  return (
    <header className="sticky top-0 z-30 border-b bg-background/80 backdrop-blur">
      <div className="container mx-auto px-4 sm:px-6 py-2 flex flex-col md:flex-row md:items-center justify-between gap-2">
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-semibold tracking-tight text-foreground">
            KotoSub
          </h1>
          <span className="hidden lg:block text-xs text-muted-foreground">
            AI subtitle translator
          </span>
        </div>
        <div className="flex items-center gap-2">
          <TabsList className="h-auto rounded-full bg-zinc-100 p-1 dark:bg-zinc-900">
            <TabsTrigger value={ViewType.TRANSLATOR} className={NAV_TRIGGER_CLASS}>
              <Languages />
              Translator
            </TabsTrigger>
            <TabsTrigger value={ViewType.SETTINGS} className={NAV_TRIGGER_CLASS}>
              <Settings />
              Settings
            </TabsTrigger>
          </TabsList>
          {/* SwitchButton owns html.dark + the reveal animation; index.html reads the key on load. */}
          <SwitchButton
            size="sm"
            showLabel={false}
            aria-label={dark ? 'Switch to light mode' : 'Switch to dark mode'}
            onThemeChange={(theme) => {
              setDark(theme === 'dark');
              try {
                localStorage.setItem(THEME_KEY, theme);
              } catch { /* private mode */ }
            }}
          />
        </div>
      </div>
    </header>
  );
};

export default Header;
