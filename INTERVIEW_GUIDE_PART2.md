# EDA Automated (Deploy) — Interview Guide Part 2: Backend Code Line-by-Line

---

## File: `backend/main.py` — The API Controller (581 lines)

This is the **brain** of the application. Every HTTP request from the browser comes here first.

---

### Lines 1-19: Imports & Environment Setup

```python
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Path, Header
```

**What each import does:**
- `FastAPI` — Creates the web application object
- `UploadFile` — Handles file uploads (CSV/Excel)
- `File(...)` — Tells FastAPI "this parameter is a file upload" (the `...` means "required")
- `Form("")` — Tells FastAPI "this parameter comes from a form field" (the `""` means "default empty")
- `HTTPException` — Used to return error responses (400, 404, 500)
- `Header` — Reads values from HTTP headers (we use this for session_id)

```python
from fastapi.responses import StreamingResponse, FileResponse, HTMLResponse
```

- `StreamingResponse` — Sends data word-by-word (used for AI streaming)
- `FileResponse` — Sends a file download (used for CSV downloads)
- `HTMLResponse` — Sends HTML content (used for serving the frontend)

```python
from pydantic import BaseModel
```

- `BaseModel` — Used to define the shape of JSON request bodies. Like a contract: "I expect these fields with these types."

```python
import polars as pl       # The data engine (like Pandas but 10x faster)
import io                 # In-memory file handling (BytesIO for CSV parsing)
import json               # Reading/writing JSON session files
import os                 # File system operations (makedirs, path.exists)
import uuid               # Generates unique session IDs
import re                 # Regular expressions (UUID validation)
import time               # Timestamps for cache-busting
from pathlib import Path as FilePath  # Object-oriented file paths
```

**Q: "Why `import pathlib as FilePath` and not just `Path`?"**
> Because FastAPI already uses `Path` for URL parameters. Naming it `FilePath` avoids the conflict.

```python
# Load .env for local development (ignored in Docker where env vars are set directly)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not required in production
```

**Q: "Why the try/except?"**
> In Docker, environment variables are set directly via `-e` flag or Render dashboard. The `python-dotenv` library isn't needed there. The try/except means the app works BOTH locally (with .env file) and in Docker (without it). If dotenv isn't installed, it silently continues.

---

### Lines 24-36: App Creation & CORS

```python
app = FastAPI(title="Automated EDA AI")
```
Creates the FastAPI application. The `title` appears in auto-generated Swagger docs at `/docs`.

```python
os.makedirs("uploads", exist_ok=True)
os.makedirs("sessions", exist_ok=True)
```
Creates `uploads/` and `sessions/` folders if they don't exist. `exist_ok=True` means "don't crash if it already exists."

---

### Lines 38-60: Session Management

```python
def is_valid_uuid(val: str):
    return bool(re.match(r'^[0-9a-f]{8}-[0-9a-f]{4}-...', str(val).lower()))
```

**What this does:** Checks if a string looks like a valid UUID (e.g., `a1b2c3d4-e5f6-7890-abcd-ef1234567890`).

**Why it matters:** Prevents **path traversal attacks**. Without this, someone could send `session_id=../../etc/passwd` and the server would try to read `/etc/passwd`. The regex ensures only hex characters and dashes in the exact UUID format are accepted.

```python
def get_session(session_id: str):
    # 1. Validate UUID format (security)
    # 2. Check both .json and .parquet files exist
    # 3. Read metadata from JSON
    # 4. Read data from Parquet (fast!)
    # 5. Return both
```

```python
def save_session(session_id: str, meta: dict, df: pl.DataFrame):
    # 1. Write metadata to JSON
    # 2. Write DataFrame to Parquet (compressed, fast)
```

**Q: "Why Parquet instead of CSV?"**
> "Parquet is a columnar binary format. A 100MB CSV becomes ~10MB Parquet. Reading 10MB Parquet takes ~50ms. Reading 100MB CSV takes ~5 seconds. For a web app where users wait for every click, this matters enormously."

---

### Lines 62-109: Upload Endpoint (The Most Important Route)

```python
@app.post("/api/upload")
async def upload_file(
    file: UploadFile = File(...),    # The CSV/Excel file (required)
    context: str = Form("")          # Business context text (optional)
):
```

**Line by line what happens:**

```python
contents = await file.read()    # Read the entire file into memory (bytes)
```
`await` is used because file reading is **asynchronous** — FastAPI doesn't block other requests while one file is being read.

```python
if file.filename.endswith('.csv'):
    df = pl.read_csv(io.BytesIO(contents), ignore_errors=True)
```
- `io.BytesIO(contents)` — Wraps raw bytes into a file-like object that Polars can read
- `ignore_errors=True` — Don't crash on malformed rows (skip them)

```python
eda_results = perform_analysis(df)              # Run full statistical analysis
encoded_preview, encoding_log = advanced_preprocessing(df)  # PII + encoding
session_id = str(uuid.uuid4())                  # Generate unique ID
```

```python
meta = {
    "context": context,        # "Predict customer churn"
    "stats": eda_results["stats"],      # Statistical summary
    "audit": eda_results["audit"],      # Data quality issues
    "num_cols": eda_results["num_cols"], # ["Sales_Amount", "Age", ...]
    "cat_cols": eda_results["cat_cols"], # ["Region", "Smoker", ...]
    "shape": eda_results["shape"]       # [1000, 8]
}
save_session(session_id, meta, df)  # Save to disk
```

**Q: "Why save to disk? Why not keep in memory?"**
> "Two reasons: (1) Memory is expensive on cloud servers (Render free tier = 512MB RAM). Parquet on disk uses almost no RAM. (2) If the server restarts, in-memory data is lost. Parquet files persist."

---

### Lines 111-125: Lazy Visual Loading

```python
@app.get("/api/visual/{session_id}/{column}")
async def get_visual(session_id: str, column: str):
```

**Q: "What is lazy loading and why use it?"**
> "Instead of generating ALL 8 chart images on upload (which would take ~10 seconds and crash the browser), we generate ZERO charts upfront. When the user scrolls to the Distributions tab, the browser uses `IntersectionObserver` to detect which chart images are visible on screen, and requests ONLY those. Each chart is generated on-demand in ~200ms. This is called 'lazy loading' — you only load what's actually needed."

---

### Lines 127-158: AI Endpoints (Streaming)

```python
@app.get("/api/ai/report")
async def get_report(session_id: str = Header(None)):
```

**Why `Header(None)` instead of query parameter?**
> "We pass session_id in the HTTP header because GET requests shouldn't have bodies, and putting UUIDs in URLs creates ugly bookmarkable links. Headers are invisible to the user."

```python
critical_audit = [issue for issue in meta["audit"] 
    if "warning" in issue['severity'].lower() 
    or "danger" in issue['severity'].lower()]
```

**Q: "What is 'Smart Context Chunking'?"**
> "AI models have a context window limit (e.g., 8K tokens for Llama 3.3). If we send ALL audit issues, the prompt exceeds the limit and gets truncated. So we filter — only send 'Warning' and 'Danger' severity issues to the AI. Informational items are excluded. This keeps the prompt small while preserving the critical information."

```python
return StreamingResponse(
    generate_initial_report(...),
    media_type="text/event-stream"
)
```

**Q: "What is streaming and why use it?"**
> "`StreamingResponse` sends data chunk-by-chunk as it's generated. The AI model generates text word-by-word — each word is sent immediately to the browser. The user sees text appearing in real-time (like ChatGPT typing). Without streaming, the user would wait 10-15 seconds for the entire response, seeing nothing. With streaming, the first word appears in ~200ms."

---

### Lines 244-301: AutoML Script Generator

```python
script = f'''"""
Auto-Generated ML Baseline Script
Target: {req.target_column}
"""
import pandas as pd
from sklearn.model_selection import train_test_split
...
'''
```

**Q: "What does this endpoint do?"**
> "It generates a complete, runnable Python script for training an ML model on the user's dataset. The user picks a target column and model type (classification/regression), and the server generates a script with `train_test_split`, `RandomForestClassifier/Regressor`, and evaluation metrics. The browser downloads it as `train_model.py`."

**Q: "Is this a real AutoML system?"**
> "No — real AutoML (like AutoGluon or TPOT) tries hundreds of models and hyperparameters. This is a 'baseline script generator' — it gives you a working starting point that you can modify. Think of it as scaffolding, not a finished building."

---

### Lines 303-325: PySpark Lazy Import

```python
spark_available = False
try:
    from backend.spark_engine import (...)
    spark_available = True
except ImportError:
    pass
```

**Q: "Why lazy import PySpark?"**
> "PySpark is NOT installed on Render (the free tier can't handle a JVM). If we used a normal `import`, the app would crash on startup. The try/except makes PySpark optional — the app starts fine without it, and the Spark tab shows 'PySpark not available' instead of crashing."

---

### Lines 547-579: Frontend Serving with Cache-Busting

```python
FRONTEND_DIR = FilePath(__file__).resolve().parent.parent / "frontend"
```

**Q: "What does this line do?"**
> `__file__` = the current file (`main.py`)
> `.resolve()` = get the absolute path
> `.parent` = go up one directory (from `backend/` to project root)
> `.parent` = unnecessary, but `/ "frontend"` adds `/frontend` to the path
> Result: `/app/frontend` (in Docker) or `/home/.../EDA_Automated_to_Deploy/frontend` (locally)

```python
@app.get("/")
async def serve_index():
    raw = (FRONTEND_DIR / "index.html").read_text(encoding="utf-8")
    ts = int(time.time() * 1000)  # Current time in milliseconds
    raw = _re.sub(r'(script\.js)(\?[^"]*)?', f'script.js?t={ts}', raw)
    raw = _re.sub(r'(style\.css)(\?[^"]*)?', f'style.css?t={ts}', raw)
```

**Q: "What is cache-busting?"**
> "Browsers cache files aggressively. If you update `script.js` on the server, users might still see the OLD version because their browser cached it. By appending `?t=1776740007278` (a unique timestamp) to every URL, the browser treats it as a NEW file and downloads it fresh. The timestamp changes every millisecond, so the browser never uses cached versions."

```python
return HTMLResponse(
    content=raw,
    headers={
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
    }
)
```

**Q: "What do these cache headers mean?"**
- `no-store` — Don't save this response to cache at all
- `no-cache` — Always check with the server before using cache
- `must-revalidate` — If the cache entry is stale, you MUST re-fetch
- `max-age=0` — The cache expires immediately
- `Pragma: no-cache` — Same as Cache-Control but for old HTTP/1.0 proxies

---

## File: `backend/ai_engine.py` — The AI Brain (120 lines)

### Lines 1-32: Dynamic AI Provider

```python
AI_PROVIDER = os.getenv("AI_PROVIDER", "groq").lower()

if AI_PROVIDER == "groq":
    from groq import AsyncGroq
    client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY", ""))
    MODEL_NAME = "llama-3.3-70b-versatile"
else:
    from openai import AsyncOpenAI
    client = AsyncOpenAI(
        base_url=os.getenv("LMSTUDIO_URL", "http://127.0.0.1:1234/v1"),
        api_key="lm-studio"
    )
    MODEL_NAME = "local-model"
```

**Q: "How does the AI provider switching work?"**
> "Both Groq and OpenAI use the **same API format** (chat completions). The Groq Python library (`AsyncGroq`) has the exact same `.chat.completions.create()` method as OpenAI's library. So the rest of the code is identical — only the client object and model name change. This is called the **Strategy Pattern** in software design."

**Q: "What is `AsyncGroq` vs `Groq`?"**
> "`AsyncGroq` is the asynchronous version. It uses Python's `async/await` to make non-blocking API calls. This means while the AI is generating a response (which takes seconds), FastAPI can handle OTHER requests simultaneously. If we used the synchronous `Groq`, the entire server would freeze while waiting for the AI."

**Q: "What does `os.getenv("GROQ_API_KEY", "")` mean?"**
> "Read the environment variable `GROQ_API_KEY`. If it's not set, use empty string as default. On Render, this is set in the dashboard. Locally, it's read from the `.env` file via `python-dotenv`."

### Lines 35-74: AI Report Generation

```python
async def generate_initial_report(data_context, stats, audit, shape):
    # ... builds a system prompt with dataset info ...
    
    stream = await client.chat.completions.create(
        model=MODEL_NAME,
        messages=messages,
        stream=True,          # ← This is what makes it stream word-by-word
        temperature=0.7,      # ← Controls randomness (0=deterministic, 1=creative)
        max_tokens=2048       # ← Maximum words in response
    )
    
    async for chunk in stream:
        if chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content   # ← Send each word immediately
```

**Q: "What is `yield` and how is it different from `return`?"**
> "`return` sends ONE response and the function ends. `yield` sends data piece-by-piece — the function pauses after each yield, waits for the next chunk from the AI, then yields again. This is called a **generator function**. FastAPI's `StreamingResponse` reads from this generator and sends each piece to the browser immediately."

**Q: "What is `temperature`?"**
> "Temperature controls randomness. At 0.0, the AI always picks the most likely next word (deterministic). At 1.0, it considers less likely words too (creative). 0.7 is a good balance — technical enough for data analysis but not too rigid."

### Lines 77-119: Chat With Data

```python
async def chat_with_data(message, history, data_context, df):
    sample = df.head(3).to_pandas().to_string()  # Show AI the first 3 rows
```

**Q: "Why only send 3 rows to the AI?"**
> "The AI doesn't need all 1000 rows — it just needs to understand the data structure. 3 rows show the column types, formats, and typical values. Sending all rows would exceed the context window and cost more tokens."

```python
for item in history[-10:]:   # Only send last 10 messages
```

**Q: "Why limit to 10 messages?"**
> "Each message adds tokens to the prompt. 10 messages ≈ 2000 tokens. If we sent all 50 messages from a long conversation, we'd hit the 8K token context limit and the AI would lose the earliest context anyway. This is called a **sliding window** approach."
