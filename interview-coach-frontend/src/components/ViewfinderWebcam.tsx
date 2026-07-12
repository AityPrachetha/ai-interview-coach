import type { RefObject } from 'react';
import type { MediaStatus } from '../hooks/useInterviewMedia';

interface ViewfinderWebcamProps {
  videoRef: RefObject<HTMLVideoElement | null>;
  status: MediaStatus;
  error: string | null;
  isRecording: boolean;
}

export function ViewfinderWebcam({ videoRef, status, error, isRecording }: ViewfinderWebcamProps) {
  return (
    <div className="viewfinder">
      <video ref={videoRef} muted playsInline autoPlay className="viewfinder-video" />

      {status !== 'ready' && (
        <div className="viewfinder-overlay">
          {status === 'requesting' && <p>Requesting camera access…</p>}
          {status === 'error' && <p>{error}</p>}
          {status === 'idle' && <p>Camera not started</p>}
        </div>
      )}

      <span className="viewfinder-bracket tl" />
      <span className="viewfinder-bracket tr" />
      <span className="viewfinder-bracket bl" />
      <span className="viewfinder-bracket br" />

      {isRecording && (
        <div className="rec-indicator">
          <span className="rec-dot" />
          REC
        </div>
      )}

      <style>{`
        .viewfinder {
          position: relative;
          width: 100%;
          aspect-ratio: 4 / 3;
          background: #0d1013;
          border-radius: 4px;
          overflow: hidden;
        }
        .viewfinder-video {
          width: 100%;
          height: 100%;
          object-fit: cover;
          transform: scaleX(-1);
        }
        .viewfinder-overlay {
          position: absolute;
          inset: 0;
          display: flex;
          align-items: center;
          justify-content: center;
          text-align: center;
          padding: 1.5rem;
          color: var(--stage-ink-soft);
          font-size: 0.9rem;
          background: rgba(13, 16, 19, 0.85);
        }
        .viewfinder-bracket {
          position: absolute;
          width: 28px;
          height: 28px;
          border: 2px solid rgba(255, 255, 255, 0.55);
        }
        .viewfinder-bracket.tl { top: 10px; left: 10px; border-right: none; border-bottom: none; }
        .viewfinder-bracket.tr { top: 10px; right: 10px; border-left: none; border-bottom: none; }
        .viewfinder-bracket.bl { bottom: 10px; left: 10px; border-right: none; border-top: none; }
        .viewfinder-bracket.br { bottom: 10px; right: 10px; border-left: none; border-top: none; }
        .rec-indicator {
          position: absolute;
          top: 14px;
          left: 50%;
          transform: translateX(-50%);
          display: flex;
          align-items: center;
          gap: 6px;
          background: rgba(13, 16, 19, 0.7);
          color: #fff;
          padding: 4px 10px;
          border-radius: 20px;
          font-family: var(--font-mono);
          font-size: 0.75rem;
          letter-spacing: 0.06em;
        }
        .rec-dot {
          width: 8px;
          height: 8px;
          border-radius: 50%;
          background: var(--rec);
          animation: rec-pulse 1.4s ease-in-out infinite;
        }
        @keyframes rec-pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.35; }
        }
      `}</style>
    </div>
  );
}
