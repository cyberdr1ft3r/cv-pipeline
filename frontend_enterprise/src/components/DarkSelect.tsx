'use client';

import * as React from 'react';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/app/components/ui/select';
import { cn } from '@/app/components/ui/utils';

export interface DarkSelectOption {
  value: string;
  label: string;
}

interface DarkSelectProps {
  value: string;
  onChange: (value: string) => void;
  options: DarkSelectOption[];
  placeholder?: string;
  className?: string;
  size?: 'sm' | 'md';
  disabled?: boolean;
  id?: string;
  /** Accessible name for the trigger — required whenever no visible <label> is associated. */
  ariaLabel?: string;
  onClick?: (e: React.MouseEvent<HTMLButtonElement>) => void;
}

export function DarkSelect({
  value,
  onChange,
  options,
  placeholder,
  className,
  size = 'md',
  disabled,
  id,
  ariaLabel,
  onClick,
}: DarkSelectProps) {
  const anchorRef = React.useRef<HTMLDivElement>(null);
  const [portalContainer, setPortalContainer] = React.useState<HTMLElement | null>(null);

  React.useEffect(() => {
    // `.admin-light-main` retints this component to the light app shell via
    // descendant CSS selectors — but Radix portals the popover to
    // document.body by default, escaping that scoping and leaving it dark.
    // Render into the nearest light shell instead so the override still applies;
    // pages with no such ancestor (e.g. the dark public site) fall through to body.
    setPortalContainer(anchorRef.current?.closest<HTMLElement>('.admin-light-main') ?? null);
  }, []);

  return (
    <div ref={anchorRef} className="contents">
    <Select value={value} onValueChange={onChange} disabled={disabled}>
      <SelectTrigger
        id={id}
        size={size === 'sm' ? 'sm' : 'default'}
        onClick={onClick}
        aria-label={ariaLabel}
        className={cn(
          'w-auto border-white/10 bg-white/[0.03] text-white shadow-none',
          'hover:border-white/20 hover:bg-white/[0.05]',
          'focus-visible:border-[#1f9d94]/50 focus-visible:ring-1 focus-visible:ring-[#1f9d94]/30',
          'data-[placeholder]:text-slate-500 [&_svg]:text-slate-400',
          // `!h-11` forces past the base `data-[size=default]:h-9` — the 36px
          // default trigger height reads visibly short next to the 44px
          // (h-11) inputs/buttons every consumer of this component sits beside.
          size === 'sm' ? 'rounded-lg text-xs' : 'rounded-xl text-sm !h-11',
          className,
        )}
      >
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent
        position="popper"
        container={portalContainer ?? undefined}
        className={cn(
          'z-[200] rounded-xl border border-white/10 bg-[#0f1419] text-white shadow-xl',
          'data-[state=open]:animate-in data-[state=closed]:animate-out',
        )}
      >
        {options.map(opt => (
          <SelectItem
            key={opt.value}
            value={opt.value}
            className={cn(
              // Plain `blue-600`/`white` on purpose, not the `#1f9d94` accent: the
              // `.admin-light-main` theme override matches literal class substrings
              // and ignores variant prefixes, so a `focus:bg-[#1f9d94]/…` class gets
              // force-applied to every item, not just the focused one.
              'cursor-pointer rounded-lg text-sm text-slate-200',
              'focus:bg-blue-600 focus:text-white',
              'data-[highlighted]:bg-blue-600 data-[highlighted]:text-white',
            )}
          >
            {opt.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
    </div>
  );
}
