import React, { useEffect, useState } from 'react';
import { SubtitleConfig } from '../types';
import { SUBTITLE_FORMATS, FONTS, POSITIONS, ICONS } from '../constants';
import CheckboxField from './ui/CheckboxField';
import FormLabel from './ui/FormLabel';
import Select from './ui/Select';

interface OptionsDrawerProps {
  config: SubtitleConfig;
  onChange: <K extends keyof SubtitleConfig>(key: K, value: SubtitleConfig[K]) => void;
  disabled?: boolean;
}

const EXPANDED_KEY = 'kotosub_options_expanded_v1';

const OptionsDrawer: React.FC<OptionsDrawerProps> = ({ config, onChange, disabled = false }) => {
  const [expanded, setExpanded] = useState<boolean>(() => {
    return localStorage.getItem(EXPANDED_KEY) === '1';
  });

  useEffect(() => {
    localStorage.setItem(EXPANDED_KEY, expanded ? '1' : '0');
  }, [expanded]);

  const activeExtras: string[] = [];
  if (config.enableDiarization) activeExtras.push('Speaker labels');
  if (config.qualityVerification) activeExtras.push('Quality check');
  if (config.burnSubtitles) activeExtras.push('Burn-in');
  activeExtras.push(config.subtitleFormat.toUpperCase());

  return (
    <div className="border border-edge rounded-2xl bg-raised overflow-hidden">
      <button
        onClick={() => setExpanded(v => !v)}
        disabled={disabled}
        aria-expanded={expanded}
        className="w-full flex items-center justify-between gap-3 px-5 py-4 text-left hover:bg-brand-soft/40 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-inset disabled:cursor-not-allowed disabled:opacity-60"
      >
        <span className="flex items-center gap-3 min-w-0">
          <span className="p-1.5 rounded-lg bg-edge/70 text-ink-soft shrink-0">
            <ICONS.Settings />
          </span>
          <span className="font-semibold text-ink">Options</span>
          <span className="hidden sm:flex items-center gap-1.5 min-w-0 overflow-hidden">
            {activeExtras.map(extra => (
              <span
                key={extra}
                className="px-2 py-0.5 rounded-full bg-edge/70 text-ink-faint text-[11px] font-semibold whitespace-nowrap"
              >
                {extra}
              </span>
            ))}
          </span>
        </span>
        <span className={`text-ink-faint transition-transform duration-200 shrink-0 ${expanded ? 'rotate-180' : ''}`}>
          <ICONS.ChevronDown />
        </span>
      </button>

      {expanded && (
        <fieldset disabled={disabled} className="px-5 pb-6 pt-1 space-y-6 border-t border-edge enter-slide-up">
          <div className="space-y-4">
            <CheckboxField
              id="diarization"
              checked={config.enableDiarization}
              onChange={(v) => onChange('enableDiarization', v)}
              label="Label each speaker"
              description="Adds speaker names to subtitles — requires a Hugging Face token in Settings"
            />
            <CheckboxField
              id="quality-check"
              checked={config.qualityVerification}
              onChange={(v) => onChange('qualityVerification', v)}
              label="Quality check"
              description="Reviews translations for accuracy (recommended)"
            />
          </div>

          <div className="space-y-2">
            <FormLabel>Subtitle format</FormLabel>
            <div className="flex gap-2" role="group" aria-label="Subtitle format">
              {SUBTITLE_FORMATS.map(f => (
                <button
                  key={f.value}
                  onClick={() => onChange('subtitleFormat', f.value as SubtitleConfig['subtitleFormat'])}
                  aria-pressed={config.subtitleFormat === f.value}
                  className={`flex-1 py-2 px-3 rounded-lg text-xs font-bold border transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-1 ${
                    config.subtitleFormat === f.value
                      ? 'bg-brand-soft border-brand/40 text-brand shadow-sm'
                      : 'bg-raised border-edge text-ink-faint hover:border-brand/40'
                  }`}
                >
                  {f.label.split(' ')[0]}
                </button>
              ))}
            </div>
          </div>

          <CheckboxField
            id="burn-subtitles"
            checked={config.burnSubtitles}
            onChange={(v) => onChange('burnSubtitles', v)}
            label="Embed subtitles in video"
            description="Bakes subtitles into the video file — takes longer to process"
          />

          {config.burnSubtitles && (
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 p-4 bg-edge/30 rounded-xl border border-edge">
              <div>
                <FormLabel htmlFor="font">Font</FormLabel>
                <Select id="font" className="text-sm py-2" value={config.font} onChange={(e) => onChange('font', e.target.value)}>
                  {FONTS.map(f => <option key={f} value={f}>{f}</option>)}
                </Select>
              </div>
              <div>
                <FormLabel htmlFor="position">Position</FormLabel>
                <Select id="position" className="text-sm py-2" value={config.position} onChange={(e) => onChange('position', e.target.value)}>
                  {POSITIONS.map(p => <option key={p} value={p}>{p}</option>)}
                </Select>
              </div>
              <div>
                <FormLabel htmlFor="font-size">Size ({config.fontSize})</FormLabel>
                <input id="font-size" type="range" min="10" max="48" className="w-full accent-brand" value={config.fontSize}
                  onChange={(e) => onChange('fontSize', parseInt(e.target.value))} aria-valuetext={`${config.fontSize}px`} />
              </div>
              <div>
                <FormLabel htmlFor="shadow">Shadow ({config.shadow})</FormLabel>
                <input id="shadow" type="range" min="0" max="5" step="0.5" className="w-full accent-brand" value={config.shadow}
                  onChange={(e) => onChange('shadow', parseFloat(e.target.value))} aria-valuetext={`${config.shadow}`} />
              </div>
              <div>
                <FormLabel htmlFor="stroke">Stroke ({config.outline})</FormLabel>
                <input id="stroke" type="range" min="0" max="5" step="0.5" className="w-full accent-brand" value={config.outline}
                  onChange={(e) => onChange('outline', parseFloat(e.target.value))} aria-valuetext={`${config.outline}`} />
              </div>
            </div>
          )}
        </fieldset>
      )}
    </div>
  );
};

export default OptionsDrawer;
