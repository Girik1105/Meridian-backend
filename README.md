<div align="center">

# Meridian - Backend

### AI-Powered Career Mentorship for Everyone

An intelligent career guidance platform that uses conversational AI to help people discover career paths, test-drive skills, and make informed decisions — especially those who've never had access to a mentor.

**[Live Demo](https://meridian-cbc.netlify.app)** | **[Frontend Repository](https://github.com/Girik1105/Meridian-frontend)**

---

*Built at HackASU 2026 — Track 3: Economic Empowerment & Education*

</div>

## The Problem

Millions of people navigate career decisions without guidance. Career counselors are scarce, expensive, or inaccessible. First-generation college students, career changers, and underserved communities are left guessing — often investing time and money into paths that don't fit them.

**Meridian bridges this gap** by providing personalized, AI-driven career mentorship that adapts to each user's unique background, constraints, and aspirations.

## What Meridian Does

1. **Conversational Onboarding** — A multi-turn AI conversation maps your background, constraints, interests, and goals into a structured profile. No forms — just a natural conversation.

2. **Career Path Discovery** — Using your profile, Meridian generates 2-3 realistic career paths with salary ranges, timelines, required skills, and ROI analysis grounded in your real constraints.

3. **Skill Tasters** — 30-minute interactive crash courses that let you "try before you commit." Read, practice, and reflect — then receive an honest AI assessment of your fit.

4. **Persistent AI Mentor** — Context-aware conversations that remember your history, reference past tasters, and evolve as you do.

## Architecture

```
┌─────────────────┐     REST + SSE      ┌─────────────────────┐
│   Next.js App   │ ◄────────────────── │   Django 5.1 API    │
│   (Frontend)    │ ──────────────────► │   (This Repo)       │
└─────────────────┘                     └──────────┬──────────┘
                                                   │
                                        ┌──────────▼──────────┐
                                        │   Claude API        │
                                        │   (Sonnet 4)        │
                                        └──────────┬──────────┘
                                                   │
                                        ┌──────────▼──────────┐
                                        │   PostgreSQL        │
                                        └─────────────────────┘
```

### How It Works

- **SSE Streaming** — Claude's responses stream in real-time via Server-Sent Events with async Django views
- **Structured Extraction** — Claude outputs natural language and structured data (career paths, profile updates) in the same response using XML-like tags. The backend parses and stores the structured data while streaming clean text to the user
- **Progressive Profile Enrichment** — Each interaction enriches the user's profile, making subsequent features smarter. Onboarding informs career discovery, which informs skill tasters, which informs the mentor
- **Context Budget Management** — A `ContextBuilder` assembles targeted prompts per feature, keeping each Claude call under ~8K tokens with conversation summarization at 20+ messages

## Tech Stack

| Layer | Technology |
|-------|------------|
| **Framework** | Django 5.1 with async views |
| **API** | Django REST Framework |
| **Auth** | JWT via `djangorestframework-simplejwt` (cookie-based) |
| **AI** | Claude API (`claude-sonnet-4-20250514`) with streaming |
| **Database** | PostgreSQL (production) / SQLite3 (development) |
| **Server** | Uvicorn (ASGI) |
| **Deployment** | Render |

## Project Structure

```
Meridian-backend/
├── meridianbackend/           # Django project configuration
│   ├── settings.py            # Environment-based config (python-decouple)
│   ├── urls.py                # Root URL routing → /api/
│   ├── asgi.py                # ASGI entry point for async streaming
│   └── wsgi.py
├── api/                       # Main application
│   ├── models.py              # 7 models (User, Profile, Conversation, Message, CareerPath, SkillTaster, TasterResponse)
│   ├── context_builder.py     # Assembles Claude context per feature
│   ├── views_auth.py          # Register, login, refresh, logout, password reset
│   ├── views_chat.py          # Chat send + SSE streaming
│   ├── views_career.py        # Career path generation, listing, selection
│   ├── views_taster.py        # Skill taster CRUD + assessment
│   ├── views_conversations.py # Conversation listing
│   ├── serializers.py         # DRF serializers
│   ├── authentication.py      # Cookie-based JWT authentication
│   ├── urls.py                # API URL routing
│   ├── signals.py             # Auto-create profile on registration
│   ├── emails.py              # Transactional email templates
│   └── admin.py               # Django admin configuration
├── prompts/                   # Claude system prompts
│   ├── onboarding.txt         # Conversational profile building
│   ├── career_discovery.txt   # Career path generation
│   ├── skill_taster.txt       # Taster content generation
│   ├── taster_help.txt        # In-taster tutoring
│   └── assessment.txt         # Post-taster honest assessment
├── requirements.txt
└── manage.py
```

## API Endpoints

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/auth/register/` | Create account, returns JWT cookies |
| `POST` | `/api/auth/login/` | Authenticate, returns JWT cookies |
| `POST` | `/api/auth/refresh/` | Refresh access token |
| `POST` | `/api/auth/logout/` | Clear auth cookies |
| `GET` | `/api/auth/me/` | Current user + profile |

### Chat
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/chat/send/` | Send message, get conversation_id |
| `GET` | `/api/chat/stream/<id>/` | SSE stream of Claude's response |

### Career Paths
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/career-paths/generate/` | Generate personalized career paths |
| `GET` | `/api/career-paths/` | List career paths |
| `POST` | `/api/career-paths/<id>/select/` | Select a path to explore |

### Skill Tasters
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/tasters/generate/` | Generate a skill taster |
| `GET` | `/api/tasters/` | List tasters |
| `GET` | `/api/tasters/<id>/` | Taster detail with responses |
| `POST` | `/api/tasters/<id>/start/` | Begin a taster |
| `POST` | `/api/tasters/<id>/respond/` | Submit module response |
| `POST` | `/api/tasters/<id>/complete/` | Complete and trigger assessment |
| `GET` | `/api/tasters/<id>/assessment/` | Get AI assessment |

## Getting Started

### Prerequisites

- Python 3.11+
- PostgreSQL (optional — SQLite works for development)
- An [Anthropic API key](https://console.anthropic.com/)

### 1. Clone and set up environment

```bash
git clone https://github.com/Girik1105/Meridian-backend.git
cd Meridian-backend
python3 -m venv venv
source venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

Create a `.env` file in the project root:

```env
DJANGO_SECRET_KEY=your-secret-key-here
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
ANTHROPIC_API_KEY=your-anthropic-api-key
FRONTEND_URL=http://localhost:3000
```

Generate a Django secret key:

```bash
python3 -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

### 4. Run migrations and start the server

```bash
python3 manage.py migrate
python3 manage.py runserver
```

The API will be available at `http://localhost:8000/api`.

> **Note:** For full functionality, you'll also need to run the [frontend](https://github.com/Girik1105/Meridian-frontend).

## Database Schema

7 tables with UUID primary keys throughout:

- **User** — Extended Django AbstractUser with UUID PK
- **UserProfile** — Progressively enriched JSON profile (education, constraints, interests, learning style)
- **Conversation** — Typed conversations (onboarding, career_discovery, skill_taster, mentor_chat)
- **Message** — Individual messages with role, content, and metadata
- **CareerPath** — AI-generated career suggestions with salary, timeline, skills, and ROI data
- **SkillTaster** — 30-minute interactive crash courses with modular content
- **TasterResponse** — User responses to taster modules with engagement tracking

## Design Philosophy

- **Empowerment over dependency** — Help users make their own informed decisions, never prescribe
- **Transparency** — Claude explicitly states it is AI, not a licensed counselor
- **No cultural assumptions** — Asks "what does a better situation look like to *you*?"
- **Honest assessments** — "This is based on a 30-minute sample. A real decision deserves more exploration."
- **Progressive intelligence** — Every interaction makes the next one smarter

## License

This project was built for HackASU 2026.
