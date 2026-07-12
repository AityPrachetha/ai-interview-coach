import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import * as api from '../api/client';
import { ApiError } from '../api/client';
import type { AnswerOut, QuestionOut } from '../api/types';
import { useInterviewMedia } from '../hooks/useInterviewMedia';
import { ViewfinderWebcam } from '../components/ViewfinderWebcam';
import { Timer } from '../components/Timer';

type Phase = 'loading' | 'asking' | 'recording' | 'submitting' | 'feedback' | 'error';

const ANSWER_TIME_LIMIT_SECONDS = 120;
const FRAME_CAPTURE_INTERVAL_MS = 1500;
const FEEDBACK_AUTO_ADVANCE_SECONDS = 4;

function speak(text: string): Promise<void> {
  return new Promise((resolve) => {
    if (!('speechSynthesis' in window)) {
      resolve();
      return;
    }
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 1;
    utterance.onend = () => resolve();
    utterance.onerror = () => resolve();
    window.speechSynthesis.speak(utterance);
  });
}

export function InterviewPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const media = useInterviewMedia();

  const [phase, setPhase] = useState<Phase>('loading');
  const [question, setQuestion] = useState<QuestionOut | null>(null);
  const [lastAnswer, setLastAnswer] = useState<AnswerOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [typedAnswer, setTypedAnswer] = useState('');
  const [showTypedFallback, setShowTypedFallback] = useState(false);
  const [autoAdvanceIn, setAutoAdvanceIn] = useState(FEEDBACK_AUTO_ADVANCE_SECONDS);

  const frameIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const stoppingRef = useRef(false);
  const questionRef = useRef<QuestionOut | null>(null);
  questionRef.current = question;

  const clearFrameCapture = useCallback(() => {
    if (frameIntervalRef.current) {
      clearInterval(frameIntervalRef.current);
      frameIntervalRef.current = null;
    }
  }, []);

  const advanceOrFinish = useCallback(
    (answer: AnswerOut) => {
      if (answer.session_status === 'COMPLETED' || !answer.next_question) {
        navigate(`/report/${sessionId}`);
        return;
      }
      setQuestion(answer.next_question);
      setLastAnswer(answer);
      setPhase('feedback');
    },
    [navigate, sessionId],
  );

  const handleStop = useCallback(async () => {
    if (stoppingRef.current || !sessionId || !questionRef.current) return;
    stoppingRef.current = true;
    clearFrameCapture();
    setPhase('submitting');
    setError(null);

    try {
      const audioBlob = await media.stopAudioRecording();
      const answer = await api.submitAnswerAudio(sessionId, questionRef.current.id, audioBlob);
      advanceOrFinish(answer);
    } catch (err) {
      const message =
        err instanceof ApiError
          ? err.message
          : 'Something went wrong submitting your answer.';
      setError(message);
      setPhase('error');
    } finally {
      stoppingRef.current = false;
    }
  }, [sessionId, media, clearFrameCapture, advanceOrFinish]);

  const handleTypedSubmit = useCallback(async () => {
    if (!sessionId || !questionRef.current || !typedAnswer.trim()) return;
    clearFrameCapture();
    setPhase('submitting');
    setError(null);
    try {
      // Voice recording started as soon as we entered the 'recording' phase;
      // since the candidate is answering by text instead, stop and discard
      // it so it isn't left running in the background.
      await media.stopAudioRecording();
      const answer = await api.submitAnswerText(sessionId, questionRef.current.id, typedAnswer.trim());
      setTypedAnswer('');
      setShowTypedFallback(false);
      advanceOrFinish(answer);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not submit your answer.');
      setPhase('error');
    }
  }, [sessionId, typedAnswer, clearFrameCapture, media, advanceOrFinish]);

  // Boot up: start camera/mic, load the first question.
  useEffect(() => {
    if (!sessionId) return;
    let cancelled = false;
    (async () => {
      await media.start();
      try {
        const next = await api.getNextQuestion(sessionId);
        if (cancelled) return;
        if (next.completed || !next.question) {
          navigate(`/report/${sessionId}`);
          return;
        }
        setQuestion(next.question);
        setPhase('asking');
      } catch (err) {
        setError(err instanceof ApiError ? err.message : 'Could not load the interview.');
        setPhase('error');
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  // Speak the question aloud, then move into the recording phase.
  useEffect(() => {
    if (phase !== 'asking' || !question) return;
    let cancelled = false;
    (async () => {
      await speak(question.text);
      if (cancelled) return;
      setPhase('recording');
    })();
    return () => {
      cancelled = true;
    };
  }, [phase, question]);

  // While recording: start audio capture + periodic frame capture to /frames.
  useEffect(() => {
    if (phase !== 'recording' || !question || !sessionId) return;
    media.startAudioRecording();

    frameIntervalRef.current = setInterval(async () => {
      const blob = await media.captureFrameBlob();
      if (!blob) return;
      try {
        await api.submitFrame(sessionId, question.id, blob);
      } catch {
        // Transient frame-analysis failures shouldn't interrupt the interview.
      }
    }, FRAME_CAPTURE_INTERVAL_MS);

    return () => clearFrameCapture();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase, question, sessionId]);

  // Feedback screen: auto-advance countdown to the next question.
  useEffect(() => {
    if (phase !== 'feedback') return;
    setAutoAdvanceIn(FEEDBACK_AUTO_ADVANCE_SECONDS);
    const interval = setInterval(() => {
      setAutoAdvanceIn((prev) => {
        if (prev <= 1) {
          clearInterval(interval);
          setPhase('asking');
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(interval);
  }, [phase]);

  // Stop any in-progress TTS if the person navigates away mid-question.
  useEffect(() => {
    return () => {
      if ('speechSynthesis' in window) window.speechSynthesis.cancel();
    };
  }, []);

  if (phase === 'error') {
    return (
      <div className="stage-page stage-center">
        <div className="card" style={{ maxWidth: 460 }}>
          <h3>Something went wrong</h3>
          <p>{error}</p>
          <button className="btn btn-primary" onClick={() => window.location.reload()}>
            Reload
          </button>
        </div>
        <style>{stageStyles}</style>
      </div>
    );
  }

  return (
    <div className="stage-page">
      <div className="stage-grid">
        <div className="stage-main">
          {phase === 'loading' ? (
            <p className="stage-status mono">Setting up your camera and microphone…</p>
          ) : (
            <>
              <p className="stage-topic mono">{question?.topic ?? 'Interview'}</p>
              <h2 className="stage-question">{question?.text}</h2>
            </>
          )}

          {phase === 'asking' && <p className="stage-status">Reading question aloud…</p>}

          {phase === 'recording' && (
            <>
              <Timer
                seconds={ANSWER_TIME_LIMIT_SECONDS}
                isRunning={phase === 'recording'}
                onExpire={handleStop}
                onStop={handleStop}
              />
              <button
                className="link-btn"
                onClick={() => setShowTypedFallback((v) => !v)}
                type="button"
              >
                {showTypedFallback ? 'Hide typed answer' : "Can't use voice? Type your answer instead"}
              </button>
              {showTypedFallback && (
                <div className="typed-fallback">
                  <textarea
                    value={typedAnswer}
                    onChange={(e) => setTypedAnswer(e.target.value)}
                    placeholder="Type your answer…"
                  />
                  <button
                    className="btn btn-secondary"
                    onClick={handleTypedSubmit}
                    disabled={!typedAnswer.trim()}
                  >
                    Submit typed answer
                  </button>
                </div>
              )}
            </>
          )}

          {phase === 'submitting' && <p className="stage-status">Scoring your answer…</p>}

          {phase === 'feedback' && lastAnswer && (
            <div className="feedback-card">
              <p className="feedback-score mono">
                Relevance: {lastAnswer.relevance_score ?? '—'} / 100
              </p>
              {lastAnswer.followup_generated && (
                <p className="feedback-note">The coach has a follow-up on that one.</p>
              )}
              <p className="feedback-advance mono">Next question in {autoAdvanceIn}s…</p>
              <button className="btn btn-secondary" onClick={() => setPhase('asking')}>
                Continue now
              </button>
            </div>
          )}
        </div>

        <div className="stage-webcam">
          <ViewfinderWebcam
            videoRef={media.videoRef}
            status={media.status}
            error={media.error}
            isRecording={phase === 'recording'}
          />
        </div>
      </div>

      <style>{stageStyles}</style>
    </div>
  );
}

const stageStyles = `
  .stage-page {
    min-height: 100%;
    background: var(--stage);
    color: var(--stage-ink);
    padding: 2.5rem 1.5rem;
  }
  .stage-center {
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .stage-status {
    color: var(--stage-ink-soft);
  }
  .stage-grid {
    max-width: 1080px;
    margin: 0 auto;
    display: grid;
    grid-template-columns: 1.3fr 1fr;
    gap: 2.5rem;
    align-items: start;
  }
  @media (max-width: 860px) {
    .stage-grid { grid-template-columns: 1fr; }
  }
  .stage-topic {
    color: var(--gold);
    font-size: 0.8rem;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    margin-bottom: 0.6rem;
  }
  .stage-question {
    font-size: 1.6rem;
    line-height: 1.35;
    color: var(--stage-ink);
    max-width: 34ch;
  }
  .link-btn {
    background: none;
    border: none;
    color: var(--stage-ink-soft);
    text-decoration: underline;
    font-size: 0.85rem;
    padding: 0;
    margin-top: 1rem;
  }
  .typed-fallback {
    margin-top: 1rem;
    display: flex;
    flex-direction: column;
    gap: 0.6rem;
  }
  .typed-fallback textarea {
    min-height: 100px;
    padding: 0.7rem;
    border-radius: var(--radius);
    border: 1px solid var(--stage-line);
    background: var(--stage-raised);
    color: var(--stage-ink);
  }
  .feedback-card {
    margin-top: 1rem;
    padding: 1.25rem;
    background: var(--stage-raised);
    border-radius: 12px;
    border: 1px solid var(--stage-line);
  }
  .feedback-score {
    font-size: 1.1rem;
    margin-bottom: 0.4rem;
  }
  .feedback-note {
    color: var(--gold);
    font-size: 0.88rem;
  }
  .feedback-advance {
    color: var(--stage-ink-soft);
    font-size: 0.82rem;
    margin: 0.8rem 0;
  }
`;
