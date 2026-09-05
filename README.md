# HelixDB

> A research & learning companion for students and researchers — learn every subject in the approach that suits *you*, built with care and compassion toward every white-hearted learner.

A FastAPI-based backend service for a college research cell: research lifecycle management, event tracking, reports, imports, OCR, scoring, and secure role-based access for **students, faculty, and researchers**.

![Python](https://img.shields.io/badge/python-3.11+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-modern-009688)
![Status](https://img.shields.io/badge/status-building_with_love-ff69b4)

---

## 💜 Why HelixDB exists

This application is aimed to assist **students and researchers to learn the subject in your approach towards it** — not a single rigid path, but the path that fits the learner. It is built with care and compassion toward every white-hearted person who keeps trying.

> I don't have much expertise or money to show my compassion and support.
> To describe me: I am just an ordinary man. Whenever I try for an opportunity or a task,
> a troll or a meme may arrive before me — and yet the heart keeps trying.
>
> I am a child raised by a mother, after losing my dad. Simply, this is me.
> The happiest time I remember is the day I first saw — and last met — my purest white heart.
>
> HelixDB is that feeling turned into code: a quiet place where a student can learn without
> fear, and a researcher can build without noise.

---

## ✨ Features

### Core Capabilities
- **🎓 Role-based access** — College Admin, Research Admin, Faculty, and Student accounts with clean permission boundaries
- **📚 Research lifecycle** — submission, scoring, and verification workflows for research work
- **📅 Events** — track research events and milestones
- **📊 Reports & analytics** — analytics, reporting, and scoring (config-driven via `scoring_config.json`)
- **📥 Imports & OCR** — import research metadata and digitize content with OCR support
- **🔐 Authentication** — JWT-based auth with a safe mock/local mode for first run
- **📝 Audit trail** — service-level audit logging for accountability

## 🏗️ Technology Stack

### Backend
- **Python 3.11+** and **FastAPI**
- **Pydantic v2 + pydantic-settings** for typed, environment-driven configuration (`HELIXDB_*`)
- **SQLite** relational schema (`researchmitra`) with automatic init on startup
- **CORS** middleware and SPA static-serving for the built frontend

### Structure
```
backend/
├── api/          # REST routers: auth, users, research, events, reports, import, OCR, settings
├── services/     # business logic: auth, research, scoring, verification, importer, OCR, analytics, audit
├── schemas/      # request/response schemas
├── database/     # relational schema + connection
├── config/       # runtime settings and scoring configuration
├── main.py       # FastAPI entry point
```

## 🚀 Quick Start

```bash
# from the repo root
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload
```

- API docs (Swagger): `http://localhost:8000/docs`
- Health check: `http://localhost:8000/api/health`
- First run creates demo accounts: `admin`, `rcadmin`, `fac100`, `stu100` (mock auth mode)

## 🤝 A Promise

No expertise, no money, and no shortcut needed to care. HelixDB is built to be **simple, forgiving, and open** — the same way one ordinary man was raised by one extraordinary mother.

*For every white heart that keeps trying — this one is for you.*