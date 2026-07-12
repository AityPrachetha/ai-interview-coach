# AI Interview Coach — Frontend

React + Vite + TypeScript frontend for the FastAPI backend. Handles auth,
resume/JD upload, a live webcam+voice mock interview, and the final report.

## Setup

```bash
npm install
npm run dev
```

Runs on `http://localhost:5173` by default. Your FastAPI backend must be
running on `http://localhost:8000` (already allowed by the backend's CORS
config) — change `VITE_API_BASE_URL` in `.env` if it's somewhere else.

## Pages

- `/login` — sign in or create an account
- `/setup` — upload resume, paste job description, pick interview type, start
- `/interview/:sessionId` — the live interview
- `/report/:sessionId` — final hiring-readiness report

## How the live interview loop works

The backend has no concept of a "live session" — it only exposes stateless
endpoints (submit an answer, submit a frame, get the next question). All of
the live-interview behavior — question read aloud, webcam running, timed
recording, auto-advance — is orchestrated entirely in
`src/pages/InterviewPage.tsx`:

1. On load: request camera+mic once (`useInterviewMedia`), fetch the first
   question via `GET /next-question`.
2. **Asking**: the question text is spoken aloud via the browser's built-in
   `SpeechSynthesis` API (free, no backend involved) and shown on screen.
   When speech finishes, move to recording.
3. **Recording**: starts an audio recording (`MediaRecorder`, audio track
   only) AND a timer (`Timer` component, 120s default) with an early
   "I'm done" stop button. While recording, a frame is captured from the
   live video every 1.5s and POSTed to
   `/interviews/{id}/questions/{qid}/frames` — this is what populates eye
   contact / expression / posture scores. Frame POST failures are swallowed
   silently so a flaky connection doesn't interrupt the interview.
4. On stop (timeout or button): audio recording is finalized and POSTed to
   `/interviews/{id}/answers/audio`. The response tells us the next question
   (if any) or that the session is complete.
5. **Feedback**: briefly shows the relevance score and whether a follow-up
   was generated, then auto-advances back to step 2 for the next question
   (or navigates to `/report/:id` if the session just completed).

There's also a "type your answer instead" fallback during recording, for
when mic/webcam access isn't available or preferred — it posts to the plain
text `/answers` endpoint instead.

## Known limitations to be aware of

- **Camera/mic permissions**: browsers require a secure context (`https://`
  or `localhost`) for `getUserMedia` — fine for local dev, will need HTTPS
  once deployed.
- **`SpeechSynthesis` voice/quality varies by browser and OS** — it's free
  and requires no backend work, but don't expect studio-quality narration.
- **This was built and type-checked in a sandbox with no camera/microphone
  hardware and no browser to click through.** The build compiles cleanly and
  the logic has been reviewed carefully, but the actual in-browser
  experience — permission prompts, autoplay behavior, real recording
  quality — needs to be verified by you on a real machine before you trust
  it end to end.
