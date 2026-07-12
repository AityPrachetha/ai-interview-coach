import { useCallback, useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import * as api from '../api/client';
import { ApiError } from '../api/client';
import type { InterviewReportOut } from '../api/types';
import { ScoreGauge } from '../components/ScoreGauge';

export function ReportPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const [report, setReport] = useState<InterviewReportOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(
    async (recompute = false) => {
      if (!sessionId) return;
      setLoading(true);
      setError(null);
      try {
        const data = await api.getReport(sessionId, recompute);
        setReport(data);
      } catch (err) {
        setError(err instanceof ApiError ? err.message : 'Could not load the report.');
      } finally {
        setLoading(false);
      }
    },
    [sessionId],
  );

  useEffect(() => {
    load();
  }, [load]);

  if (loading && !report) {
    return (
      <div className="report-page">
        <p className="mono">Loading report…</p>
      </div>
    );
  }

  if (error && !report) {
    return (
      <div className="report-page">
        <div className="error-banner">{error}</div>
        <Link to="/setup" className="btn btn-secondary">
          Back to setup
        </Link>
      </div>
    );
  }

  if (!report) return null;

  const coveragePct = Math.round(report.weight_coverage * 100);

  return (
    <div className="report-page">
      <header className="report-header">
        <p className="eyebrow">Interview report</p>
        <h1>Hiring readiness</h1>
        {report.is_preliminary && (
          <div className="preliminary-badge">
            Preliminary — {report.questions_answered} of {report.total_questions} questions
            answered so far
          </div>
        )}
      </header>

      <section className="card headline-card">
        <div className="headline-score">
          <span className="mono headline-number">
            {report.hiring_readiness_score !== null ? Math.round(report.hiring_readiness_score) : '—'}
          </span>
          <span className="headline-suffix">/ 100</span>
        </div>
        <p className="coverage-note">
          Based on {coveragePct}% of scoring categories
          {report.is_preliminary ? ' — final score will use more data once the interview is complete.' : '.'}
        </p>
        <button className="btn btn-secondary" onClick={() => load(true)} disabled={loading}>
          {loading ? 'Recomputing…' : 'Recompute report'}
        </button>
      </section>

      <section className="gauge-row">
        <ScoreGauge label="Communication" value={report.communication_score} />
        <ScoreGauge label="Confidence" value={report.confidence_score} />
        <ScoreGauge label="Technical" value={report.technical_score} />
        <ScoreGauge label="Behavioral" value={report.behavioral_score} />
        <ScoreGauge label="Resume match" value={report.resume_match_score} />
      </section>

      {report.improvement_suggestions.length > 0 && (
        <section className="card">
          <h3>Where to improve</h3>
          <ul className="suggestion-list">
            {report.improvement_suggestions.map((s, i) => (
              <li key={i}>
                <strong>{s.area}:</strong> {s.suggestion}
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="card">
        <h3>Question by question</h3>
        <div className="qa-list">
          {report.questions.map((q) => (
            <div className="qa-item" key={q.question_id}>
              <div className="qa-item-header">
                <span className="qa-topic mono">{q.topic ?? 'General'}</span>
                {q.is_followup && <span className="qa-followup-tag">follow-up</span>}
                <span className="qa-relevance mono">{q.relevance_score ?? '—'}/100</span>
              </div>
              <p className="qa-question">{q.question_text}</p>
              <p className="qa-transcript">{q.transcript}</p>
              <div className="qa-signals mono">
                {q.speaking_pace_wpm !== null && <span>{q.speaking_pace_wpm} wpm</span>}
                {q.filler_word_count !== null && <span>{q.filler_word_count} fillers</span>}
                {q.voice_confidence_score !== null && <span>voice {q.voice_confidence_score}</span>}
                {q.eye_contact_score !== null && <span>eye contact {q.eye_contact_score}</span>}
                {q.posture_score !== null && <span>posture {q.posture_score}</span>}
              </div>
            </div>
          ))}
        </div>
      </section>

      <style>{`
        .report-page {
          max-width: 860px;
          margin: 0 auto;
          padding: 3rem 1.5rem 5rem;
          display: flex;
          flex-direction: column;
          gap: 1.5rem;
        }
        .eyebrow {
          font-family: var(--font-mono);
          font-size: 0.75rem;
          letter-spacing: 0.08em;
          text-transform: uppercase;
          color: var(--accent-strong);
        }
        .preliminary-badge {
          display: inline-block;
          background: var(--accent-tint);
          color: var(--accent-strong);
          font-size: 0.82rem;
          padding: 0.3rem 0.8rem;
          border-radius: 20px;
          margin-top: 0.5rem;
        }
        .headline-card {
          text-align: center;
        }
        .headline-score {
          display: flex;
          align-items: baseline;
          justify-content: center;
          gap: 0.3rem;
        }
        .headline-number {
          font-size: 3.5rem;
          font-weight: 600;
          color: var(--accent-strong);
        }
        .headline-suffix {
          color: var(--ink-soft);
          font-size: 1.1rem;
        }
        .coverage-note {
          color: var(--ink-soft);
          font-size: 0.88rem;
          margin: 0.5rem 0 1.25rem;
        }
        .gauge-row {
          display: flex;
          flex-wrap: wrap;
          justify-content: center;
          gap: 1.5rem;
          padding: 0.5rem 0;
        }
        .suggestion-list {
          padding-left: 1.2rem;
          margin: 0;
        }
        .suggestion-list li {
          margin-bottom: 0.7rem;
          line-height: 1.5;
        }
        .qa-list {
          display: flex;
          flex-direction: column;
          gap: 1.25rem;
        }
        .qa-item {
          border-top: 1px solid var(--line);
          padding-top: 1rem;
        }
        .qa-item-header {
          display: flex;
          align-items: center;
          gap: 0.6rem;
          margin-bottom: 0.4rem;
        }
        .qa-topic {
          color: var(--accent-strong);
          font-size: 0.78rem;
        }
        .qa-followup-tag {
          font-size: 0.72rem;
          background: var(--accent-tint);
          color: var(--accent-strong);
          padding: 0.1rem 0.5rem;
          border-radius: 10px;
        }
        .qa-relevance {
          margin-left: auto;
          font-size: 0.85rem;
          color: var(--ink-soft);
        }
        .qa-question {
          font-weight: 500;
          margin-bottom: 0.3rem;
        }
        .qa-transcript {
          color: var(--ink-soft);
          font-size: 0.9rem;
        }
        .qa-signals {
          display: flex;
          gap: 1rem;
          flex-wrap: wrap;
          font-size: 0.78rem;
          color: var(--ink-soft);
        }
      `}</style>
    </div>
  );
}
