# Future Roadmap & Deployment Guide

This document outlines how to take this platform from a local tool to a monetized, publicly deployed SaaS product.

## 1. Preparing for GitHub
Before pushing this code to a public repository, ensure you:
1. **Create a `.gitignore`:**
   ```text
   venv/
   sessions/
   __pycache__/
   .env
   ml_ready_dataset.csv
   ```
2. **Remove Hardcoded URLs:** The `ai_engine.py` hardcodes `http://127.0.0.1:1234/v1`. Change this to use `os.getenv("OPENAI_API_BASE", "http://127.0.0.1:1234/v1")`.

## 2. Monetization Strategy (SaaS)
To turn this into a paid service:
- **Authentication:** Implement `OAuth2` (e.g., Google Sign-in) using a library like `Auth0` or `Supabase`.
- **Database Migration:** Instead of local `/sessions/*.parquet` files, store the data in an S3 bucket (AWS) or Google Cloud Storage. Use a PostgreSQL database to map `user_id` -> `session_id`.
- **Payment Gateway:** Integrate **Stripe**. Offer a Free Tier (datasets up to 10MB) and a Premium Tier (datasets up to 500MB, unlocked Auto-ML generator).
- **TTL (Time to Live):** Implement a cron job or Celery worker that deletes session files older than 24 hours to prevent cloud storage costs from ballooning.

## 3. Deployment Architecture (Docker & Cloud)
### Dockerization
Create a `Dockerfile`:
```dockerfile
FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8080
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

### Cloud Providers
- **Render / Heroku (Easy):** You can directly connect your GitHub repo to Render. It will automatically build the Dockerfile and deploy the API.
- **AWS (Enterprise):** 
  - Host the FastAPI backend on **AWS ECS** or **App Runner**.
  - Host the Frontend on **Vercel** or **AWS S3/CloudFront** (requires decoupling the static mount in `main.py`).
  - Route the LLM API calls to **OpenAI GPT-4o** or **Anthropic Claude 3.5 Sonnet** (LM Studio is only for local dev).

## 4. Next-Level Features to Build
- **Multi-Table Joins:** Allow users to upload multiple CSVs and automatically detect foreign keys to merge them.
- **Time Series Forecasting:** Add a module specifically for date-based data to predict future trends using ARIMA/Prophet.
- **Drag & Drop Dashboard:** Allow users to resize and move charts around on the UI.
