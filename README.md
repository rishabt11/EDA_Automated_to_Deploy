# 🚀 Data Engineer Pro — AI-Powered EDA Platform

An enterprise-grade Automated Exploratory Data Analysis platform powered by **Polars**, **FastAPI**, and **Groq AI**.

Upload any CSV/Excel dataset and instantly get:
- 🔍 **Data Quality Audit** — Missing values, skewness, PII detection
- 📊 **Interactive Visualizations** — Lazy-loaded distribution charts, scatter plots, PCA
- 🤖 **AI Strategy Reports** — Powered by Groq's Llama 3.3 70B
- 🔧 **Transformation Studio** — 13+ data transformations (log, normalize, encode, etc.)
- ⚡ **PySpark Operations** — Window functions, GroupBy, Filter (when available)
- 📥 **Auto-ML Script Generator** — Download ready-to-run sklearn scripts

---

## 🌐 Live Demo

**Deployed on Render:** [https://eda-automated.onrender.com](https://eda-automated.onrender.com)

> ⚠️ Free tier — first load may take 30-60 seconds if the service was idle.

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | FastAPI + Uvicorn |
| **Data Engine** | Polars (handles millions of rows) |
| **AI** | Groq Cloud API (Llama 3.3 70B) |
| **Frontend** | Vanilla JS + CSS (glassmorphism, responsive) |
| **Container** | Docker |
| **Deployment** | Render (Docker) |

---

## 🏃 Quick Start (Local)

### 1. Clone & Setup
```bash
git clone https://github.com/rishabh11022002/EDA_Automated_to_Deploy.git
cd EDA_Automated_to_Deploy

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

pip install -r requirements.txt
```

### 2. Configure Environment
```bash
cp .env.example .env
# Edit .env and add your Groq API key
```

Get a **free** Groq API key at: [console.groq.com](https://console.groq.com)

### 3. Run
```bash
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8080
```

Open: **http://localhost:8080**

---

## 🐳 Docker

```bash
# Build
docker build -t eda-platform .

# Run
docker run -p 8080:8080 \
  -e GROQ_API_KEY=your_key_here \
  -e AI_PROVIDER=groq \
  eda-platform
```

Open: **http://localhost:8080**

---

## ☁️ Deploy to Render

### Step 1: Push to GitHub
```bash
git add -A
git commit -m "Deploy-ready: fixes + Render config"
git push origin main
```

### Step 2: Create Render Web Service
1. Go to [render.com](https://render.com) → Sign in with GitHub
2. Click **"New +"** → **"Web Service"**
3. Connect your **EDA_Automated_to_Deploy** repo
4. Configure:
   - **Name:** `eda-automated` (or any name)
   - **Environment:** `Docker`
   - **Instance Type:** `Free`
5. Add **Environment Variables:**
   | Key | Value |
   |---|---|
   | `GROQ_API_KEY` | `gsk_your_key_here` |
   | `AI_PROVIDER` | `groq` |
6. Click **"Deploy Web Service"**

Your app will be live at: `https://your-app-name.onrender.com`

---

## 📁 Project Structure

```
EDA_Automated_to_Deploy/
├── backend/
│   ├── main.py          # FastAPI routes + session management
│   ├── eda_engine.py    # Polars-based EDA (stats, charts, PCA, transforms)
│   ├── ai_engine.py     # Groq AI (streaming reports + chat)
│   └── spark_engine.py  # PySpark operations (optional)
├── frontend/
│   ├── index.html       # Single-page app UI
│   ├── script.js        # All browser logic
│   └── style.css        # Glassmorphism + responsive CSS
├── Dockerfile           # Production container
├── requirements.txt     # Python dependencies
├── .env.example         # Environment variable template
└── README.md
```

---

## 🔑 Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `GROQ_API_KEY` | Yes | — | Free API key from [console.groq.com](https://console.groq.com) |
| `AI_PROVIDER` | No | `groq` | `groq` (cloud) or `lmstudio` (local) |
| `PORT` | No | `8080` | Server port (Render sets this automatically) |

---

## 📄 License

Personal project by Rishabh — Built for learning and portfolio demonstration.
