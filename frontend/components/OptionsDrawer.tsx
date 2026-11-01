import React, { useEffect, useState } from 'react';
import { SubtitleConfig } from '../types';
import { SUBTITLE_FORMATS, FONTS, POSITIONS } from '../constants';
import { ChevronDown, Settings } from 'lucide-react';
import { cn } from '@/lib/utils';
import CheckboxField from './ui/CheckboxField';
import FormLabel from './ui/FormLabel';
import { Badge } from '@/components/ui/badge';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Slider } from '@/components/ui/slider';
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group';

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
  if (config.enableDiarization) activeExtras.push('Speaker dashes');
  if (config.qualityVerification) activeExtras.push('Quality check');
  if (config.burnSubtitles) activeExtras.push('Burn-in');
  activeExtras.push(config.subtitleFormat.toUpperCase());

  return (
    <Collapsible open={expanded} onOpenChange={setExpanded} disabled={disabled} className="rounded-xl border bg-card">
      <CollapsibleTrigger className="flex w-full items-center justify-between gap-3 rounded-xl px-5 py-4 text-left transition-colors hover:bg-accent/50 focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50 disabled:cursor-not-allowed disabled:opacity-60">
        <span className="flex items-center gap-3 min-w-0">
          <span className="rounded-lg bg-muted p-1.5 text-muted-foreground">
            <Settings className="size-4" />
          </span>
          <span className="font-semibold text-foreground">Options</span>
          <span className="hidden sm:flex items-center gap-1.5 min-w-0 overflow-hidden">
            {activeExtras.map(extra => (
              <Badge key={extra} variant="secondary">{extra}</Badge>
            ))}
          </span>
        </span>
        <ChevronDown
          className={cn(
            'size-4 shrink-0 text-muted-foreground transition-transform duration-200',
            expanded && 'rotate-180'
          )}
        />
      </CollapsibleTrigger>

      <CollapsibleContent>
        <fieldset disabled={disabled} className="space-y-6 border-t px-5 pb-6 pt-4 enter-slide-up">
          <div className="space-y-4">
            <CheckboxField
              id="diarization"
              checked={config.enableDiarization}
              onChange={(v) => onChange('enableDiarization', v)}
              label="Separate speakers"
              description="Starts a new subtitle line (marked with –) whenever the voice changes — requires a Hugging Face token in Settings"
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
            <ToggleGroup
              type="single"
              variant="outline"
              value={config.subtitleFormat}
              onValueChange={(v) => {
                if (v) onChange('subtitleFormat', v as SubtitleConfig['subtitleFormat']);
              }}
              aria-label="Subtitle format"
              className="w-full"
            >
              {SUBTITLE_FORMATS.map(f => (
                <ToggleGroupItem key={f.value} value={f.value} className="flex-1 text-xs">
                  {f.label.split(' ')[0]}
                </ToggleGroupItem>
              ))}
            </ToggleGroup>
          </div>

          <CheckboxField
            id="burn-subtitles"
            checked={config.burnSubtitles}
            onChange={(v) => onChange('burnSubtitles', v)}
            label="Embed subtitles in video"
            description="Bakes subtitles into the video file — takes longer to process"
          />

          {config.burnSubtitles && (
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 rounded-lg border bg-muted/50 p-4">
              <div>
                <FormLabel htmlFor="font">Font</FormLabel>
                <Select value={config.font} onValueChange={(v) => onChange('font', v)}>
                  <SelectTrigger id="font" size="sm" className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {FONTS.map(f => <SelectItem key={f} value={f}>{f}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <FormLabel htmlFor="position">Position</FormLabel>
                <Select value={config.position} onValueChange={(v) => onChange('position', v)}>
                  <SelectTrigger id="position" size="sm" className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {POSITIONS.map(p => <SelectItem key={p} value={p}>{p}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <FormLabel>Size ({config.fontSize})</FormLabel>
                <Slider
                  min={10}
                  max={48}
                  step={1}
                  value={[config.fontSize]}
                  onValueChange={([v]) => onChange('fontSize', v)}
                  aria-label="Font size"
                  disabled={disabled}
                />
              </div>
              <div>
                <FormLabel>Shadow ({config.shadow})</FormLabel>
                <Slider
                  min={0}
                  max={5}
                  step={0.5}
                  value={[config.shadow]}
                  onValueChange={([v]) => onChange('shadow', v)}
                  aria-label="Shadow"
                  disabled={disabled}
                />
              </div>
              <div>
                <FormLabel>Stroke ({config.outline})</FormLabel>
                <Slider
                  min={0}
                  max={5}
                  step={0.5}
                  value={[config.outline]}
                  onValueChange={([v]) => onChange('outline', v)}
                  aria-label="Stroke"
                  disabled={disabled}
                />
              </div>
            </div>
          )}
        </fieldset>
      </CollapsibleContent>
    </Collapsible>
  );
};

export default OptionsDrawer;
