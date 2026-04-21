# EDA Automated (Deploy) — Interview Guide Part 1: Architecture & Big Picture

---

## What Is This Project? (One-Line Answer)

> "An AI-powered web platform deployed on Render via Docker that automates Exploratory Data Analysis — you upload a CSV, and it instantly audits data quality, generates visualizations, runs PCA, applies transformations, and lets you chat with an AI about your data using Groq's Llama 3.3 70B model."

---

## The Complete Architecture (Like You're 5)

Imagine a restaurant:
- **Frontend (index.html + script.js + style.css)** = The menu + the dining room. What the customer sees.
- **Backend (main.py)** = The waiter. Takes orders from the customer, goes to the kitchen, brings food back.
- **EDA Engine (eda_engine.py)** = The kitchen. Does the actual cooking (data analysis).
- **AI Engine (ai_engine.py)** = The sommelier. Gives expert recommendations (AI-powered insights).
- **Spark Engine (spark_engine.py)** = The specialty chef. Handles big data operations (optional).
- **Docker** = The food truck. Packages the entire restaurant so it works identically anywhere.
- **Render** = The parking spot. Where the food truck is parked so customers can find it on the internet.

### How Data Flows (Step by Step)

```
User Browser                    FastAPI Server                  Groq Cloud
    │                               │                               │
    │  1. Upload CSV file           │                               │
    │ ─────────────────────────────>│                               │
    │                               │  2. Polars reads CSV          │
    │                               │  3. perform_analysis()        │
    │                               │  4. Save session (.parquet)   │
    │  5. Return audit + stats      │                               │
    │ <─────────────────────────────│                               │
    │                               │                               │
    │  6. Request AI report         │                               │
    │ ─────────────────────────────>│  7. Send data context ──────> │
    │                               │  8. Stream AI response <───── │
    │  9. Display streaming text    │                               │
    │ <─────────────────────────────│                               │
    │                               │                               │
    │  10. Lazy-load chart for      │                               │
    │      column "Sales_Amount"    │                               │
    │ ─────────────────────────────>│  11. Generate matplotlib PNG  │
    │  12. Display chart            │                               │
    │ <─────────────────────────────│                               │
```

---

## Project File Structure (What Each File Does)

```
EDA_Automated_to_Deploy/
│
├── backend/                     ← All Python server code
│   ├── main.py                  ← The WAITER: FastAPI routes, session management
│   ├── eda_engine.py            ← The KITCHEN: All data analysis (Polars + Pandas)
│   ├── ai_engine.py             ← The SOMMELIER: Groq AI streaming chat
│   ├── spark_engine.py          ← The SPECIALTY CHEF: PySpark operations
│   └── eda_engine_pandas.py     ← Legacy pandas version (unused backup)
│
├── frontend/                    ← All browser code
│   ├── index.html               ← The HTML structure (what user sees)
│   ├── script.js                ← The BRAIN: All button clicks, API calls, charts
│   └── style.css                ← The LOOK: Colors, glassmorphism, dark mode
│
├── Dockerfile                   ← Recipe to build the Docker container
├── .dockerignore                ← Files Docker should NOT copy
├── .gitignore                   ← Files Git should NOT track
├── .env.example                 ← Template for environment variables
├── requirements.txt             ← Python libraries needed
└── README.md                    ← Documentation
```

---

## Tech Stack — Why Each Technology Was Chosen

### Q: "What technologies does this project use and why?"

| Technology | What It Does | Why This One (Not Alternatives) |
|---|---|---|
| **FastAPI** | Web framework (backend) | 3x faster than Flask, built-in async, auto-generates Swagger docs |
| **Polars** | Data processing engine | 10-50x faster than Pandas for large datasets, zero-copy, Rust-based |
| **Pandas** | Used for chart rendering only | Matplotlib/Seaborn require Pandas DataFrames — Polars can't be used directly |
| **Groq AI** | Cloud AI (Llama 3.3 70B) | Free tier, 10x faster inference than OpenAI, no GPU needed |
| **Matplotlib + Seaborn** | Chart generation | Industry standard, renders server-side to PNG (no JS charting library needed) |
| **Scikit-Learn** | PCA + ML script generation | Standard ML library, used for StandardScaler + PCA |
| **Docker** | Containerization | "Works on my machine" problem solved — identical everywhere |
| **Render** | Cloud hosting | Free tier, native Docker support, auto-deploy from GitHub |
| **Parquet** | Session storage format | 10x smaller than CSV, 100x faster to read, preserves data types |
| **UUID** | Session IDs | Universally unique, impossible to guess → security |

### Q: "Why Polars instead of Pandas?"

> "Polars is a Rust-based DataFrame library that uses lazy evaluation and multi-threaded execution. For a 1M row dataset, Polars finishes in ~200ms where Pandas takes ~5 seconds. Since this is a web app where users wait for every response, speed is critical. I still use Pandas for chart rendering because Matplotlib and Seaborn only accept Pandas DataFrames — but I convert only the minimum needed columns at the last moment."

### Q: "Why Groq instead of OpenAI?"

> "Three reasons: (1) Groq is free — no API costs for a portfolio project. (2) Groq uses dedicated LPU hardware that's 10x faster than GPU inference — responses stream in real-time. (3) Both Groq and OpenAI use the same chat completions API format, so switching between them is a one-line config change (just swap the client object)."

### Q: "Why Docker?"

> "Docker solves the 'works on my machine' problem. My app uses Python 3.11, Polars, Pandas, Matplotlib (which needs system-level libpng), and specific library versions. Without Docker, anyone trying to run this would spend hours debugging dependency issues. With Docker, one command builds and runs everything identically on any OS."

---

## Session Management — How User Data is Tracked

### Q: "How do you manage user sessions?"

```python
# When a user uploads a CSV:
session_id = str(uuid.uuid4())  # e.g., "a1b2c3d4-e5f6-7890-abcd-ef1234567890"

# Two files are saved:
# 1. sessions/a1b2c3d4-....json  ← Metadata (stats, audit results, column types)
# 2. sessions/a1b2c3d4-....parquet  ← Actual data (compressed binary format)
```

**Why TWO files?**
- **JSON** = Small metadata. Fast to read. Contains audit results, column names, stats — things the API needs frequently.
- **Parquet** = The actual data. Polars reads parquet 100x faster than CSV, and the file is 10x smaller.

**Why UUID?**
- UUIDs are 128-bit random numbers — the chance of collision is 1 in 2^128 (practically impossible).
- They can't be guessed — a user can't access another user's session by trying sequential IDs.

### Q: "Is this secure?"

```python
def is_valid_uuid(val: str):
    return bool(re.match(r'^[0-9a-f]{8}-[0-9a-f]{4}-...', str(val).lower()))
```

> "Yes, there's a UUID validation function that prevents **path traversal attacks**. If someone sends `session_id=../../etc/passwd`, the regex rejects it immediately. Only valid UUID format is accepted."

---

## What is CORS and Why Do We Need It?

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # Allow requests from any domain
    allow_credentials=True,
    allow_methods=["*"],      # Allow GET, POST, PUT, DELETE
    allow_headers=["*"],      # Allow any custom headers
)
```

### Q: "What is CORS?"

> "CORS stands for Cross-Origin Resource Sharing. Browsers block requests from one domain to another by default (security feature). If our frontend is at `example.com` and our API is at `api.example.com`, the browser would block it. CORS headers tell the browser: 'It's okay, allow this request.'"

### Q: "Why `allow_origins=["*"]`? Isn't that insecure?"

> "For a portfolio project deployed as a single service (frontend + backend on same URL), `*` is fine because there IS no cross-origin request — everything is on the same domain. In production with separate frontend/backend services, you'd whitelist specific domains."

---

## The 14 API Endpoints (Complete List)

| # | Method | Path | What It Does |
|---|---|---|---|
| 1 | POST | `/api/upload` | Upload CSV/Excel → run full EDA |
| 2 | GET | `/api/visual/{session}/{col}` | Lazy-load one distribution chart |
| 3 | GET | `/api/ai/report` | Stream AI strategy report |
| 4 | POST | `/api/ai/chat` | Chat with AI about your data |
| 5 | POST | `/api/chart` | Generate custom scatter/box/violin/bar/line plot |
| 6 | POST | `/api/pca` | Run PCA dimensionality reduction |
| 7 | GET | `/api/synthetic` | Generate 1000-row demo dataset |
| 8 | GET | `/api/clean` | Auto-clean dataset for ML |
| 9 | POST | `/api/transform` | Apply transformation (log, scale, encode, etc.) |
| 10 | POST | `/api/automl` | Generate downloadable ML training script |
| 11-17 | POST | `/api/spark/*` | PySpark operations (filter, groupby, window, etc.) |
| 18 | GET | `/` | Serve frontend HTML with cache-busting |
| 19 | GET | `/{filename}` | Serve static files (CSS, JS) |

---

## Interview Questions on Architecture

### Q: "Walk me through what happens when a user clicks 'Generate Demo Data'."

> 1. Browser calls `GET /api/synthetic` — the server generates a 1000-row CSV using NumPy random data
> 2. Browser receives the CSV file as a download
> 3. Browser wraps it in a `FormData` object and calls `POST /api/upload`
> 4. Server reads the CSV with `pl.read_csv()` (Polars)
> 5. `perform_analysis()` runs — calculates stats, null counts, skewness, correlation heatmap
> 6. `advanced_preprocessing()` runs — detects PII, encodes categoricals, generates preview
> 7. A UUID session is created, data saved as `.parquet`, metadata as `.json`
> 8. Response sent back with audit table, stats, correlation image, column lists
> 9. Browser renders the dashboard — switches from upload screen to dashboard screen
> 10. Browser calls `GET /api/ai/report` — AI streams a strategy report word-by-word
> 11. Browser uses IntersectionObserver to lazy-load chart images as user scrolls

### Q: "What's the difference between your personal and deploy version?"

| Feature | Personal (`EDA_Automated`) | Deploy (`EDA_Automated_to_Deploy`) |
|---|---|---|
| AI Provider | LM Studio (localhost:1234) | Groq Cloud (free API) |
| Config | Hardcoded | Environment variables (.env) |
| Container | No Docker | Dockerfile + .dockerignore |
| CSS | Desktop only | Mobile-responsive |
| Hosting | Local only | Render (cloud) |
| Caching | Had browser cache issues | Timestamp injection (no cache ever) |
