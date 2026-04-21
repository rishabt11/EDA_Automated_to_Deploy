# EDA Automated (Deploy) — Interview Guide Part 4: Docker, Render, DevOps & Frontend

---

## Part A: Dockerfile — Line by Line

```dockerfile
FROM python:3.11-slim
```
**Q: "What is a FROM instruction?"**
> "Every Docker image is built on top of another image. `python:3.11-slim` is an official image with Python 3.11 pre-installed on Debian Linux. The `slim` variant is ~120MB vs ~900MB for the full version — it excludes docs, man pages, and build tools we don't need."

**Q: "Why Python 3.11 specifically?"**
> "3.11 has the best performance/compatibility balance. 3.12+ has some library compatibility issues with older packages. 3.10 lacks some Polars features."

```dockerfile
WORKDIR /app
```
> "Sets the working directory inside the container. All subsequent `COPY`, `RUN`, and `CMD` commands execute from `/app`. Like running `cd /app` before every command."

```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*
```
**Q: "What does each piece do?"**
- `apt-get update` — Refresh the package index (required before installing)
- `build-essential` — C compiler needed by some Python packages (numpy, polars)
- `curl` — HTTP client needed for the health check
- `--no-install-recommends` — Skip optional packages → smaller image
- `rm -rf /var/lib/apt/lists/*` — Delete the package index cache → save ~50MB

**Q: "Why chain commands with `&&`?"**
> "Each `RUN` creates a Docker **layer**. If `apt-get update` and `apt-get install` were separate RUN commands, the first layer would contain the 50MB package cache permanently. By chaining with `&&` and cleaning up in the same RUN, all three steps happen in ONE layer — the final layer has no cache."

```dockerfile
ENV MPLBACKEND=Agg
```
> "Sets an environment variable inside the container. Tells matplotlib to use the 'Agg' (non-GUI) rendering backend. Same as `matplotlib.use('Agg')` in Python but applied globally."

```dockerfile
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
```
**Q: "Why copy requirements.txt BEFORE copying the app code?"**
> "Docker caching! Docker caches each layer. If I copy ALL code first, then install requirements, every code change (even changing a comment) would re-install all packages (5 minutes). By copying requirements.txt first, packages are only re-installed when requirements.txt changes. Code changes skip the pip install step entirely."

**Q: "What does `--no-cache-dir` do?"**
> "Pip normally caches downloaded packages in `~/.cache/pip` for faster re-installs. Inside Docker, we never re-install — each build is fresh. The cache would just waste ~200MB of image space."

```dockerfile
COPY . .
```
> "Copy EVERYTHING from the current directory (except files in `.dockerignore`) into `/app` inside the container."

```dockerfile
RUN mkdir -p sessions uploads
```
> "Create directories for session data and uploaded files. `-p` means 'don't error if they already exist.'"

```dockerfile
ENV PORT=8080
EXPOSE ${PORT}
```
**Q: "What's the difference between ENV and EXPOSE?"**
- `ENV PORT=8080` — Sets a variable the app can read (`os.getenv("PORT")`)
- `EXPOSE 8080` — Documentation only! It tells humans/tools which port the app uses. It does NOT actually open the port.

**Q: "How does Render handle the port?"**
> "Render sets its own `PORT` environment variable (e.g., PORT=10000). Since our Dockerfile uses `ENV PORT=8080` as default but the CMD reads `${PORT}`, Render's injected PORT overrides the default."

```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:${PORT}/api/spark/status || exit 1
```
**Q: "What is a health check?"**
> "Every 30 seconds, Docker runs this curl command. If the API responds, the container is 'healthy'. If it fails 3 times in a row, the container is marked 'unhealthy' and the platform (Render/Kubernetes) restarts it. It's like a heartbeat monitor."

**Q: "Why check `/api/spark/status`?"**
> "It's the lightest endpoint — just returns `{\"available\": false}`. No database access, no computation, no auth needed. Perfect for health checks."

```dockerfile
CMD uvicorn backend.main:app --host 0.0.0.0 --port ${PORT}
```
**Q: "What does each part mean?"**
- `uvicorn` — ASGI server (the thing that actually handles HTTP connections)
- `backend.main:app` — Import the `app` object from `backend/main.py`
- `--host 0.0.0.0` — Listen on ALL network interfaces (required in Docker, otherwise only localhost works)
- `--port ${PORT}` — Listen on the PORT variable's value
- Shell form (not exec form `["uvicorn", ...]`) — So `${PORT}` gets expanded by bash

---

## Part B: .dockerignore and .gitignore

### .dockerignore
```
venv/          ← Don't copy the 500MB virtual environment
sessions/      ← Don't copy local session data
uploads/       ← Don't copy uploaded files
__pycache__/   ← Don't copy Python bytecode cache
*.pyc          ← Don't copy compiled Python files
.env           ← DON'T copy secrets!
.git/          ← Don't copy git history (huge!)
```

**Q: "What happens if you DON'T have a .dockerignore?"**
> "The `COPY . .` command would copy EVERYTHING — including the 500MB venv, .git history, and your .env file with secrets. The Docker image would be 2GB instead of 500MB, and your API key would be baked into the image."

### .gitignore
```
venv/          ← Virtual environment (each dev creates their own)
sessions/      ← User data (privacy)
uploads/       ← User files (privacy + size)
__pycache__/   ← Auto-generated bytecode
*.pyc          ← Compiled Python
.env           ← SECRETS! Never commit API keys
.env.*         ← .env.local, .env.production, etc.
!.env.example  ← BUT DO commit the template (shows required vars)
ml_ready_dataset.csv  ← Generated output files
*.parquet      ← Binary data files
```

**Q: "What does `!.env.example` mean?"**
> "The `!` negates a rule. `.env.*` ignores ALL .env files. But `!.env.example` says 'except .env.example — DO track that one.' The example file is safe because it contains placeholder values, not real secrets."

---

## Part C: Render Deployment

### Q: "Explain how Render deployment works."

> "Render connects to the GitHub repository, clones the code, reads the `Dockerfile`, builds a Docker image in their cloud, and runs the container. It injects environment variables (like `GROQ_API_KEY`) at runtime. The URL is assigned automatically (e.g., `your-app.onrender.com`)."

### Flow:
```
Git Push → GitHub → Render detects push → Builds Docker image → Runs container → Live URL
```

### Q: "What is a cold start?"

> "Render's free tier stops the container after 15 minutes of no traffic. When someone visits after that, Render must rebuild/restart the container — this takes 30-60 seconds. It's called a 'cold start.' Paid tier ($7/mo) keeps the container running 24/7."

### Q: "How are secrets managed?"

> "The `GROQ_API_KEY` is set in Render's dashboard under 'Environment Variables.' It's injected into the Docker container at runtime via `-e GROQ_API_KEY=xxx`. It's NEVER committed to GitHub, never baked into the Docker image. If someone clones the repo, they get `.env.example` which says `GROQ_API_KEY=your_key_here` — they must get their own key."

---

### Q: "Why Render and not Railway?"

> "Both are modern PaaS platforms, but Render's free tier is genuinely free forever with no credit card required, while Railway gives you a one-time $5 credit that runs out. For a portfolio project that needs to stay live indefinitely, Render is the better choice."

**Full Comparison:**

| Feature | Render (We Used This) | Railway |
|---|---|---|
| **Free Tier** | Truly free — no credit card, no time limit | $5 one-time credit → runs out in ~2 weeks |
| **After Free Tier** | App stays live (just slower cold starts) | App STOPS — must add payment |
| **Docker Support** | Native Dockerfile detection | Native Dockerfile detection |
| **Cold Start** | ~30-60 sec after 15 min idle | ~5-10 sec (faster, but costs money) |
| **Custom Domain** | ✅ Free | ✅ Free |
| **Auto-Deploy** | ✅ On git push | ✅ On git push |
| **Env Variables** | ✅ Dashboard UI | ✅ Dashboard UI |
| **RAM (Free)** | 512 MB | 512 MB (but uses your $5 credit) |
| **Disk** | Ephemeral (resets on restart) | Ephemeral |
| **Best For** | Portfolio projects, demos | Startups with budget |

**Q: "What are the downsides of Render free tier?"**
> "Three things: (1) **Cold starts** — after 15 minutes of no traffic, the container stops. Next visit takes 30-60 seconds to boot. (2) **Ephemeral disk** — files saved during runtime (session parquet files, uploaded CSVs) are deleted on restart. For this project that's fine because sessions are temporary. (3) **Limited CPU** — free tier gets 0.1 CPU, so heavy analysis on large datasets would be slow."

**Q: "When would you choose Railway instead?"**
> "If I had budget ($5-20/mo) and needed: faster cold starts, persistent disk storage, or a production app with real users. Railway's paid tier is excellent — it charges per usage (CPU seconds + memory), so you only pay for what you use."

**Q: "What about Vercel or Netlify?"**
> "Those are for frontend-only (static sites, Next.js). Our app has a Python FastAPI backend with file uploads, matplotlib chart generation, and AI streaming — it needs a full server, not a serverless function. Render and Railway both provide full Docker-based servers."

---

## Part D: Frontend (HTML + JS + CSS)

### index.html Structure

```
index.html
├── Upload Screen (#upload-screen)
│   ├── File input
│   ├── Business context textarea
│   ├── "Analyze & Audit Data" button
│   └── "Generate Demo Data" button
│
└── Dashboard Screen (#dashboard-screen)
    ├── Header (theme toggle, export PDF, auto-clean, new dataset)
    ├── Left Panel (.data-panel)
    │   ├── Tab: 🚨 Audit & Preprocessing
    │   │   ├── Scorecard (rows, missing, skewed)
    │   │   ├── Audit Table
    │   │   ├── Transformation Studio (13 operations)
    │   │   └── ML Preprocessing Preview
    │   ├── Tab: 📊 Distributions (lazy-loaded charts)
    │   ├── Tab: 🔍 Deep Insights (custom chart builder)
    │   ├── Tab: 🎯 PCA & Correlation
    │   ├── Tab: 🧠 Auto-ML Generator
    │   └── Tab: ⚡ Spark Operations
    │
    └── Right Panel (.chat-panel)
        ├── AI Chat Header
        ├── Chat History (scrollable)
        └── Chat Input + Send/Stop buttons
```

### Q: "How do the tabs work?"
```javascript
// When a tab button is clicked:
document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        // 1. Remove 'active' class from all tabs and panes
        // 2. Add 'active' class to clicked tab and its target pane
        // 3. The CSS hides non-active panes with display:none
    });
});
```

### Q: "How does the resizable panel work?"

```javascript
// The #dragMe handle between left and right panels
resizer.addEventListener('mousedown', (e) => {
    // Start tracking mouse movement
    document.addEventListener('mousemove', resize);
});

function resize(e) {
    // Calculate new width based on mouse position
    leftPanel.style.width = e.clientX + 'px';
    // Right panel automatically fills remaining space (CSS flexbox)
}
```

### Q: "How does AI streaming work in the browser?"

```javascript
const response = await fetch('/api/ai/report', {headers: {'session-id': sessionId}});
const reader = response.body.getReader();
const decoder = new TextDecoder();

while (true) {
    const {done, value} = await reader.read();
    if (done) break;
    const text = decoder.decode(value);
    chatDiv.innerHTML += text;  // Append each word as it arrives
}
```

> "The browser uses the Fetch API with `ReadableStream`. Instead of waiting for the entire response, it reads chunks as they arrive from the server. Each chunk is a few words from the AI. We append them to the chat div immediately — creating the 'typing' effect."

### CSS Glassmorphism

```css
.glass-panel {
    background: rgba(30, 41, 59, 0.8);       /* Semi-transparent dark */
    backdrop-filter: blur(20px);              /* Blur the background behind */
    border: 1px solid rgba(148, 163, 184, 0.1); /* Subtle border */
    border-radius: 16px;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
}
```

**Q: "What is glassmorphism?"**
> "A design trend where elements look like frosted glass — semi-transparent background with a blur effect. `backdrop-filter: blur(20px)` blurs whatever is behind the element, creating a premium, modern look."

### Mobile Responsiveness

```css
@media (max-width: 768px) {
    .dashboard-layout {
        flex-direction: column;    /* Stack panels vertically */
    }
    .chat-panel {
        width: 100%;
        height: 400px;
    }
}
```

**Q: "How does mobile responsiveness work?"**
> "CSS `@media` queries detect the screen width. Below 768px (phone/tablet), the layout switches from side-by-side (flex-row) to stacked (flex-column). The chat panel goes from a sidebar to a full-width section below the data panel."

---

## Part E: Common Interview Questions (Rapid Fire)

### Q: "What would you improve?"
> "1. Add Redis for session storage (currently file-based → doesn't scale horizontally). 2. Add WebSocket for real-time progress on long-running transforms. 3. Add authentication (OAuth2 via FastAPI). 4. Replace PySpark tab with DuckDB (lighter, works everywhere). 5. Add data versioning so users can undo transformations."

### Q: "How would this handle 10 million rows?"
> "Polars handles 10M rows natively via lazy evaluation and multi-threaded processing. The bottleneck would be chart generation (matplotlib is single-threaded) and memory. I'd add server-side pagination, pre-aggregate data for charts, and use Polars lazy frames instead of eager frames."

### Q: "What if 1000 users upload files simultaneously?"
> "Current architecture: each upload creates a Parquet file on disk. With 1000 concurrent users, disk I/O becomes the bottleneck. Solutions: (1) Move to cloud storage (S3/GCS), (2) Use Redis for session metadata, (3) Deploy behind a load balancer with multiple container replicas, (4) Add rate limiting via FastAPI middleware."

### Q: "Walk me through a security concern."
> "If session_id validation wasn't there, an attacker could send `session_id=../../etc/passwd` and the server would try to read `/etc/passwd`. The UUID regex validation prevents this **path traversal attack**. Also, the GROQ_API_KEY is never in the codebase — it's injected via environment variables, so cloning the repo doesn't expose secrets."

### Q: "How is this different from just using a Jupyter notebook?"
> "A notebook is for one person, on one machine, one time. This platform: (1) Has a GUI — non-technical stakeholders can use it. (2) Auto-generates the entire audit — no manual code needed. (3) Has AI chat — ask questions in English. (4) Is deployed — accessible via URL, no Python installation needed. (5) Applies transformations live — the audit updates instantly."
