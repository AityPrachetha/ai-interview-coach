import { useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import * as api from '../api/client';
import { ApiError } from '../api/client';
import type { InterviewType } from '../api/types';

export function SetupPage() {
  const navigate = useNavigate();

  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [resumeId, setResumeId] = useState<string | null>(null);
  const [resumeUploading, setResumeUploading] = useState(false);
  const [resumeSkillCount, setResumeSkillCount] = useState<number | null>(null);

  const [jdTitle, setJdTitle] = useState('');
  const [jdCompany, setJdCompany] = useState('');
  const [jdText, setJdText] = useState('');
  const [jdId, setJdId] = useState<string | null>(null);
  const [jdSaving, setJdSaving] = useState(false);

  const [interviewType, setInterviewType] = useState<InterviewType>('BEHAVIORAL');
  const [starting, setStarting] = useState(false);

  const [error, setError] = useState<string | null>(null);

  async function handleResumeUpload() {
    if (!resumeFile) return;
    setError(null);
    setResumeUploading(true);
    try {
      const resume = await api.uploadResume(resumeFile);
      setResumeId(resume.id);
      const skills = resume.extracted_skills?.['skills'];
      setResumeSkillCount(Array.isArray(skills) ? skills.length : null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not upload resume.');
    } finally {
      setResumeUploading(false);
    }
  }

  async function handleJdSave(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setJdSaving(true);
    try {
      const jd = await api.createJobDescription({
        title: jdTitle,
        company: jdCompany,
        raw_text: jdText,
      });
      setJdId(jd.id);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not save job description.');
    } finally {
      setJdSaving(false);
    }
  }

  async function handleStart() {
    if (!resumeId || !jdId) return;
    setError(null);
    setStarting(true);
    try {
      const session = await api.createInterview({
        resume_id: resumeId,
        job_description_id: jdId,
        interview_type: interviewType,
      });
      navigate(`/interview/${session.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not start the interview.');
      setStarting(false);
    }
  }

  const canStart = !!resumeId && !!jdId && !starting;

  return (
    <div className="setup-page">
      <header className="setup-header">
        <p className="eyebrow">AI Interview Coach</p>
        <h1>Set up your mock interview</h1>
        <p className="subhead">Upload your resume and the job you're preparing for, then choose an interview style.</p>
      </header>

      {error && <div className="error-banner">{error}</div>}

      <div className="setup-grid">
        <section className="card step">
          <div className="step-heading">
            <span className="step-index mono">01</span>
            <h3>Resume</h3>
          </div>
          <div className="field">
            <label htmlFor="resume-file">Upload your resume (PDF or DOCX)</label>
            <input
              id="resume-file"
              type="file"
              accept=".pdf,.docx"
              onChange={(e) => setResumeFile(e.target.files?.[0] ?? null)}
            />
          </div>
          <button
            className="btn btn-secondary"
            onClick={handleResumeUpload}
            disabled={!resumeFile || resumeUploading || !!resumeId}
          >
            {resumeId ? 'Uploaded ✓' : resumeUploading ? 'Uploading…' : 'Upload resume'}
          </button>
          {resumeId && (
            <p className="step-confirm">
              Parsed{resumeSkillCount !== null ? ` — found ${resumeSkillCount} skills` : ''}.
            </p>
          )}
        </section>

        <section className="card step">
          <div className="step-heading">
            <span className="step-index mono">02</span>
            <h3>Job description</h3>
          </div>
          <form onSubmit={handleJdSave}>
            <div className="field">
              <label htmlFor="jd-title">Role title</label>
              <input
                id="jd-title"
                type="text"
                value={jdTitle}
                onChange={(e) => setJdTitle(e.target.value)}
                placeholder="Backend Developer Intern"
              />
            </div>
            <div className="field">
              <label htmlFor="jd-company">Company</label>
              <input
                id="jd-company"
                type="text"
                value={jdCompany}
                onChange={(e) => setJdCompany(e.target.value)}
                placeholder="Acme Corp"
              />
            </div>
            <div className="field">
              <label htmlFor="jd-text">Job description text</label>
              <textarea
                id="jd-text"
                required
                value={jdText}
                onChange={(e) => setJdText(e.target.value)}
                placeholder="Paste the full job description here…"
              />
            </div>
            <button
              type="submit"
              className="btn btn-secondary"
              disabled={jdSaving || !jdText.trim() || !!jdId}
            >
              {jdId ? 'Saved ✓' : jdSaving ? 'Saving…' : 'Save job description'}
            </button>
          </form>
        </section>

        <section className="card step">
          <div className="step-heading">
            <span className="step-index mono">03</span>
            <h3>Interview style</h3>
          </div>
          <div className="field">
            <label htmlFor="interview-type">Choose a focus</label>
            <select
              id="interview-type"
              value={interviewType}
              onChange={(e) => setInterviewType(e.target.value as InterviewType)}
            >
              <option value="BEHAVIORAL">Behavioral</option>
              <option value="TECHNICAL">Technical</option>
              <option value="HR">HR / motivational</option>
            </select>
          </div>
          <button className="btn btn-primary" onClick={handleStart} disabled={!canStart}>
            {starting ? 'Starting…' : 'Start interview'}
          </button>
        </section>
      </div>

      <style>{`
        .setup-page {
          max-width: 900px;
          margin: 0 auto;
          padding: 3rem 1.5rem 4rem;
        }
        .setup-header { margin-bottom: 2rem; }
        .eyebrow {
          font-family: var(--font-mono);
          font-size: 0.75rem;
          letter-spacing: 0.08em;
          text-transform: uppercase;
          color: var(--accent-strong);
        }
        .subhead { color: var(--ink-soft); max-width: 56ch; }
        .setup-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
          gap: 1.25rem;
        }
        .step-heading {
          display: flex;
          align-items: baseline;
          gap: 0.6rem;
          margin-bottom: 1rem;
        }
        .step-index {
          color: var(--ink-soft);
          font-size: 0.85rem;
        }
        .step-confirm {
          color: var(--accent-strong);
          font-size: 0.85rem;
          margin-top: 0.6rem;
          margin-bottom: 0;
        }
      `}</style>
    </div>
  );
}
