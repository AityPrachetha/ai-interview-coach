# 🤖 AI Interview Coach

> A next-generation AI-powered mock interview platform that simulates real technical, HR, and behavioral interviews using Large Language Models, Computer Vision, and Speech Analysis.

---

# 🚀 Overview

AI Interview Coach conducts an end-to-end interview experience similar to a real interviewer.

The system analyzes the candidate's resume, compares it with a job description, generates personalized interview questions, conducts a live interview using voice and webcam, evaluates the candidate's responses, and finally generates a comprehensive hiring-readiness report.

---

# ✨ Features

### Authentication

- User Registration
- Secure Login (JWT Authentication)

### Resume Analysis

- Upload Resume (PDF/DOCX)
- Automatic Resume Parsing
- Skill Extraction
- Resume-JD Matching

### Interview Generation

Choose interview type:

- HR Interview
- Technical Interview
- Behavioral Interview

The AI automatically generates personalized interview questions based on:

- Resume
- Job Description
- Selected Interview Type

---

# 🎙️ Live AI Interview

During the interview, the system evaluates multiple aspects of the candidate.

## Voice Analysis

- Speech-to-Text
- Speaking Pace
- Voice Confidence
- Filler Word Detection

## Computer Vision

Using MediaPipe + OpenCV:

- Eye Contact
- Facial Expressions
- Head Pose
- Posture Analysis

## AI Evaluation

The LLM evaluates:

- Technical Accuracy
- Answer Relevance
- STAR Method (Behavioral)
- Communication Quality

---

# 📊 Final Interview Report

After completing the interview, the candidate receives:

- Resume Match Score
- Technical Knowledge Score
- Communication Score
- Confidence Score
- Behavioral Score
- Hiring Readiness Score
- Personalized Improvement Suggestions

---

# 🏗️ System Architecture

```
                     Resume
                        │
                        ▼
                 Resume Parser
                        │
                        ▼
               Skill Extraction
                        │
                        ▼
                 Job Description
                        │
                        ▼
                 Match Calculation
                        │
                        ▼
           AI Question Generation
                        │
                        ▼
          Live Interview Session
      ┌──────────────┬──────────────┐
      ▼              ▼              ▼
 Voice Analysis  Computer Vision  LLM Evaluation
      └──────────────┬──────────────┘
                     ▼
             Final AI Report
```

---

# 🛠️ Tech Stack

## Frontend

- React
- TypeScript
- Vite
- Tailwind CSS

## Backend

- FastAPI
- SQLAlchemy
- PostgreSQL
- JWT Authentication

## AI

- Google Gemini / GPT
- Prompt Engineering

## Computer Vision

- MediaPipe
- OpenCV

## Speech Processing

- Whisper
- Speech Recognition

## Database

- PostgreSQL

## Deployment

- Docker
- AWS (planned)
- Vercel (Frontend)
- Render (Backend)

---

# 📁 Project Structure

```
AI-Interview-Coach
│
├── backend
│   ├── app
│   ├── requirements.txt
│   └── README.md
│
├── interview-coach-frontend
│   ├── src
│   ├── public
│   ├── package.json
│   └── README.md
│
└── README.md
```

---

# 🔄 Project Workflow

```
User Login
      │
      ▼
Upload Resume
      │
      ▼
Paste Job Description
      │
      ▼
Choose Interview Type
      │
      ▼
Resume Parsing
      │
      ▼
Skill Extraction
      │
      ▼
Question Generation
      │
      ▼
Live Interview
      │
      ▼
Voice + Vision Analysis
      │
      ▼
LLM Evaluation
      │
      ▼
Final Hiring Report
```

---

# 🧩 Current Features

- Resume Upload
- Job Description Upload
- Resume Matching
- AI Question Generation
- Live Voice Interview
- Webcam Frame Analysis
- Speech-to-Text
- Adaptive Question Flow
- AI Evaluation Report
- Hiring Readiness Score

---

# 🚧 Planned Enhancements

- Company-Specific Interview Modes
- Coding Interview Environment
- STAR Evaluation Improvements
- Dashboard with Progress Tracking
- Interview History
- Analytics Across Sessions
- Docker Deployment
- AWS Cloud Deployment

---

# 👨‍💻 Author

**Aity Prachetha**

B.Tech – Computer Science & Artificial Intelligence

Amrita Vishwa Vidyapeetham

---

# ⭐ Future Scope

This project aims to become a complete AI-powered interview preparation platform capable of conducting realistic mock interviews while providing actionable insights to help candidates improve their performance over time.
