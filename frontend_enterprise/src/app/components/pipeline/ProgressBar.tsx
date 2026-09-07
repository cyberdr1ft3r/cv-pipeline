interface ProgressBarProps {
  value: number;
  label?: string;
  showPercentage?: boolean;
}

export function ProgressBar({ value, label, showPercentage = true }: ProgressBarProps) {
  const clampedValue = Math.min(100, Math.max(0, value));
  
  return (
    <div className="space-y-2">
      {(label || showPercentage) && (
        <div className="flex justify-between text-sm">
          {label && <span className="text-slate-300">{label}</span>}
          {showPercentage && (
            <span className="text-cyan-300 font-semibold">{clampedValue.toFixed(0)}%</span>
          )}
        </div>
      )}
      <div className="h-3 w-full overflow-hidden rounded-full bg-white/10">
        <div 
          className="h-full rounded-full bg-gradient-to-r from-cyan-500 to-teal-400 transition-all duration-500 ease-out"
          style={{ width: `${clampedValue}%` }}
        />
      </div>
    </div>
  );
}