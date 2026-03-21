# Meridian Backend

Django REST API for Meridian — an AI-powered career mentor.

## Setup

### 1. Create and activate a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

Create a `.env` file in the project root:

```
DJANGO_SECRET_KEY=your-secret-key-here
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
ANTHROPIC_API_KEY=your-anthropic-api-key
```

Generate a secret key:

```bash
python3 -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

### 4. Run migrations

```bash
python3 manage.py migrate
```

### 5. Start the server

```bash
python3 manage.py runserver
```

The API will be available at `http://localhost:8000/api`.
