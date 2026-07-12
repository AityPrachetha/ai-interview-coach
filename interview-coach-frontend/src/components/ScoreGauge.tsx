interface ScoreGaugeProps {
  label: string;
  value: number | null;
  size?: number;
}

export function ScoreGauge({ label, value, size = 96 }: ScoreGaugeProps) {
  const radius = (size - 10) / 2;
  const circumference = Math.PI * radius; // half circle
  const pct = value === null ? 0 : Math.max(0, Math.min(100, value));
  const dashOffset = circumference * (1 - pct / 100);

  return (
    <div className="gauge">
      <svg width={size} height={size / 2 + 10} viewBox={`0 0 ${size} ${size / 2 + 10}`}>
        <path
          d={`M 5 ${size / 2 + 5} A ${radius} ${radius} 0 0 1 ${size - 5} ${size / 2 + 5}`}
          fill="none"
          stroke="var(--line)"
          strokeWidth="8"
          strokeLinecap="round"
        />
        {value !== null && (
          <path
            d={`M 5 ${size / 2 + 5} A ${radius} ${radius} 0 0 1 ${size - 5} ${size / 2 + 5}`}
            fill="none"
            stroke="var(--accent)"
            strokeWidth="8"
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={dashOffset}
          />
        )}
      </svg>
      <div className="gauge-value mono">{value === null ? '—' : Math.round(value)}</div>
      <div className="gauge-label">{label}</div>

      <style>{`
        .gauge {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 0.2rem;
        }
        .gauge-value {
          font-size: 1.3rem;
          font-weight: 600;
          margin-top: -0.6rem;
          color: var(--ink);
        }
        .gauge-label {
          font-size: 0.78rem;
          color: var(--ink-soft);
          text-align: center;
        }
      `}</style>
    </div>
  );
}
