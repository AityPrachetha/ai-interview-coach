import { useEffect, useRef, useState } from 'react';

interface TimerProps {
  seconds: number;
  isRunning: boolean;
  onExpire: () => void;
  onStop: () => void;
}

function formatTime(totalSeconds: number): string {
  const m = Math.floor(totalSeconds / 60);
  const s = totalSeconds % 60;
  return `${m}:${s.toString().padStart(2, '0')}`;
}

export function Timer({ seconds, isRunning, onExpire, onStop }: TimerProps) {
  const [remaining, setRemaining] = useState(seconds);
  const onExpireRef = useRef(onExpire);
  onExpireRef.current = onExpire;

  useEffect(() => {
    setRemaining(seconds);
  }, [seconds]);

  useEffect(() => {
    if (!isRunning) return;
    const interval = setInterval(() => {
      setRemaining((prev) => {
        if (prev <= 1) {
          clearInterval(interval);
          onExpireRef.current();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(interval);
  }, [isRunning]);

  const isLow = remaining <= 10;

  return (
    <div className="timer-row">
      <span className={`mono timer-display ${isLow ? 'timer-low' : ''}`}>{formatTime(remaining)}</span>
      <button className="btn btn-danger" onClick={onStop} disabled={!isRunning}>
        I'm done
      </button>

      <style>{`
        .timer-row {
          display: flex;
          align-items: center;
          gap: 1rem;
        }
        .timer-display {
          font-size: 1.4rem;
          font-weight: 500;
          color: var(--stage-ink);
          min-width: 3ch;
        }
        .timer-low {
          color: var(--rec);
        }
      `}</style>
    </div>
  );
}
