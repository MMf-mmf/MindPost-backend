# MindPost — Backend

> **Turn your voice into content.** MindPost lets you record voice notes on the go, automatically transcribes them, stores them as searchable embeddings, and lets you chat with your notes or generate social media posts with a single tap.

---

## 📱 What It Does

1. **Record** — Hit record in the mobile app or web app, speak your thoughts.
2. **Transcribe** — Audio is sent to the backend where OpenAI Whisper transcribes it automatically.
3. **Embed** — The transcript is converted into a vector embedding (OpenAI `text-embedding-*`) and stored in PostgreSQL with `pgvector`.
4. **Chat** — Ask questions across all your voice notes using a RAG (Retrieval-Augmented Generation) chat interface ("remind me about the person I met in Greece").
5. **Post** — Select one or more voice notes and generate a social media post with AI. Edit it and publish directly to **X (Twitter)** from the app.

---

## 🏗️ Architecture

```
Mobile App (React Native)  ──┐
                             ├──▶  Django REST API  ──▶  PostgreSQL + pgvector
Web App (Django Templates)  ──┘         │
                                        ├──▶  OpenAI   (Whisper + Embeddings + Chat)
                                        ├──▶  X API    (OAuth 2.0 + 1.0a posting)
                                        ├──▶  Stripe   (Subscriptions)
                                        ├──▶  Mailgun  (Transactional email)
                                        └──▶  GCS      (Audio file storage)
```

**Deployed on Google Cloud Run** with Cloud SQL (PostgreSQL), Google Cloud Storage for media, and Google Cloud Secret Manager for secrets.

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| **Backend Framework** | Django 4.x |
| **REST API** | Django REST Framework + JWT (SimpleJWT) |
| **Database** | PostgreSQL + `pgvector` extension |
| **Vector Search** | pgvector (cosine similarity for RAG) |
| **AI / ML** | OpenAI Whisper (transcription), OpenAI Embeddings, OpenAI Chat Completions |
| **Social Posting** | X (Twitter) API v2 OAuth 2.0 + v1.1 OAuth 1.0a (media upload) |
| **Payments** | Stripe (subscription tiers: Basic / Pro) |
| **Email** | Mailgun via django-anymail |
| **File Storage** | Google Cloud Storage |
| **Secret Management** | Google Cloud Secret Manager |
| **Containerisation** | Docker + Docker Compose |
| **CI/CD** | Google Cloud Build |
| **Deployment** | Google Cloud Run |
| **Web Frontend** | Django Templates + HTMX + Alpine.js + Tailwind CSS |
| **Admin** | Unfold (custom Django admin theme) |

---

## ✨ Features

### Voice Notes (Brain Dumps)
- Record audio directly from the mobile app or web browser
- Automatic transcription via OpenAI Whisper on upload
- Edit transcripts after the fact
- Auto-tagging with `#hashtags` extracted from transcript content
- Encrypted transcript storage at rest

### AI Chat (RAG)
- Ask natural language questions across all your voice notes
- Semantic search via pgvector cosine similarity
- Returns relevant note excerpts as context for the LLM
- Per-user conversation state with rate limiting

### Social Post Generation
- Select one or more voice notes as source material
- AI generates platform-optimised post content
- Multiple post variants returned for selection
- Supports configurable character limits (Basic: 280, Pro: 25,000)
- Edit generated content before publishing
- Draft / Published status workflow
- Publish directly to **X (Twitter)** via OAuth 2.0
- Image attachment support via Twitter OAuth 1.0a media upload

### Subscriptions & Rate Limiting
- Two tiers: **Basic** ($15/mo) and **Pro** ($30/mo)
- Stripe payment integration with webhooks
- Per-user rate limits enforced server-side:
  - Recordings per month
  - Max recording length
  - Post generations per month
  - Chat messages per month
- Limits block usage gracefully with informative errors

### Authentication & Security
- JWT authentication (access + refresh tokens) for the mobile API
- Session-based authentication for the web app
- Token rotation and blacklisting
- API rate throttling (DRF throttle classes)
- Encrypted OAuth token storage (X API credentials per user)

### X / Twitter Integration
- OAuth 2.0 PKCE flow for per-user authorisation
- OAuth 1.0a support for media (image) uploads
- Encrypted token storage in the database
- Token refresh handling

---

## 📂 Project Structure

```
mindpost-backend/
├── project/
│   ├── settings/
│   │   ├── base.py          # Shared settings
│   │   ├── local.py         # Local development
│   │   ├── staging.py       # Staging environment
│   │   └── prod.py          # Production (GCP Secret Manager)
│   ├── urls.py
│   └── wsgi.py
├── brain_dump_app/          # Core app: recordings, transcription, embeddings, posts
│   ├── models.py            # BrainDump, Post, TwitterConnection, PostImage
│   ├── api.py               # DRF ViewSets (mobile API)
│   ├── views.py             # Django views (web)
│   ├── tasks.py             # Background processing
│   └── x_api.py             # X/Twitter API integration
├── users_app/               # Custom user model, auth views
├── subscriptions_app/       # Stripe subscription management
├── whatsapp_app/            # WhatsApp integration (experimental)
├── utils/
│   ├── prompts.py           # AI prompt templates
│   └── convert_audio.py     # Audio pre-processing
├── templates/               # Django HTML templates (web frontend)
├── static/                  # CSS, JS, images
├── docs/
│   └── api/api_docs.md      # Full REST API documentation
├── Dockerfile
├── docker-compose.yml       # Local dev with Cloud SQL proxy
├── cloudbuild.yaml          # GCP Cloud Build CI/CD pipeline
├── .env.example             # Required environment variables reference
└── manage.py
```

---

## 🚀 Getting Started (Local Development)

### Prerequisites
- Python 3.11+
- PostgreSQL with the `pgvector` extension enabled
- Docker & Docker Compose (optional, for Cloud SQL proxy)
- A GCP project with Cloud Storage (optional for local dev)

### 1. Clone & set up the environment

```bash
git clone https://github.com/MMf-mmf/MindPost-backend.git
cd MindPost-backend

python -m venv .venv
source .venv/bin/activate
pip install -r project/requirements/local.txt
```

### 2. Configure environment variables

```bash
cp .env.example .env
# Edit .env and fill in your values
```

At minimum for local development you need:
- `DJANGO_SECRET_KEY`
- `OPENAI_API_KEY`
- `PRODUCTION_DATABASE_*` (or configure a local DB block in `local.py`)
- `MAIL_GUN_API_KEY`

### 3. Set up the database

Enable `pgvector` on your PostgreSQL instance:
```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

Run migrations:
```bash
python manage.py migrate
```

### 4. Run the development server

```bash
python manage.py runserver
```

### 5. Run with Docker Compose (Cloud SQL proxy)

```bash
# Update docker-compose.yml with your Cloud SQL instance name
docker-compose up --build
```

---

## 🐳 Docker

The `Dockerfile` uses a multi-stage build targeting Python 3.11. The `docker-compose.yml` spins up:
- **web** — Django app via Gunicorn
- **cloudsqlproxy** — Google Cloud SQL Auth Proxy for local → Cloud SQL connectivity

---

## ☁️ Deployment (Google Cloud Run)

The `cloudbuild.yaml` defines the full CI/CD pipeline:

1. Build Docker image and push to Artifact Registry
2. Run `makemigrations` and `migrate` via `exec-wrapper`
3. Run `collectstatic`
4. Deploy to Cloud Run

Secrets are managed via **Google Cloud Secret Manager**. The production settings file (`prod.py`) fetches the `.env` content and GCS credentials from Secret Manager at startup.

---

## 📖 API Documentation

Full REST API docs are in [`docs/api/api_docs.md`](docs/api/api_docs.md).

Base URL: `/api/`

Authentication: `Authorization: Bearer <jwt_access_token>`

Key endpoints:

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/token/` | Obtain JWT token pair |
| `POST` | `/api/token/refresh/` | Refresh access token |
| `GET/POST` | `/api/brain-dumps/` | List / create voice notes |
| `GET/PATCH/DELETE` | `/api/brain-dumps/{uuid}/` | Retrieve / update / delete a note |
| `POST` | `/api/posts/generate_from_dumps/` | Generate social post from notes |
| `GET/POST` | `/api/posts/` | List / create posts |
| `GET` | `/api/twitter-connection/status/` | Check X connection status |

---

## 📸 Screenshots

> _Coming soon — mobile app and web app screenshots_

---

## 🗺️ Roadmap

- [ ] Background task queue (Celery / Cloud Tasks) for async transcription
- [ ] LinkedIn integration
- [ ] Android app publishing
- [ ] Stateful multi-turn chat conversations
- [ ] FastAPI migration for async performance

---

## 📄 License

This project is licensed under the [MIT License](LICENSE) — free to use, modify, and distribute.