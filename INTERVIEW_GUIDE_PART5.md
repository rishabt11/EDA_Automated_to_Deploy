# EDA Automated (Deploy) — Interview Guide Part 5: COMPLETE FLOW — Every Step Traced

This guide traces **every single user action** from button click → JavaScript → HTTP request → Python backend → response → browser rendering. Nothing is skipped.

---

## FLOW 1: User Opens the Website

### What happens when someone visits `https://your-app.onrender.com`?

```
Step 1: Browser sends GET / to the server

Step 2: FastAPI route @app.get("/") in main.py catches it
        └── serve_index() runs
        
Step 3: Server reads frontend/index.html from disk
        raw = (FRONTEND_DIR / "index.html").read_text(encoding="utf-8")
        
Step 4: Cache-busting injection
        ts = int(time.time() * 1000)  → e.g., 1776740007278
        Replaces: <script src="script.js">
        With:     <script src="script.js?t=1776740007278">
        Same for style.css
        WHY? So the browser never uses a cached old version
        
Step 5: Server returns HTMLResponse with no-cache headers
        Cache-Control: no-store, no-cache, must-revalidate, max-age=0
        
Step 6: Browser receives index.html
        ├── Parses the HTML structure
        ├── Requests style.css?t=1776740007278  (GET /{filename:path})
        │   └── serve_static() returns the CSS file with no-cache headers
        └── Requests script.js?t=1776740007278  (GET /{filename:path})
            └── serve_static() returns the JS file with no-cache headers

Step 7: script.js executes immediately
        ├── Line 1:   const API_BASE = "/api"  → sets the base URL for all API calls
        ├── Lines 4-14: Grabs all HTML elements by their IDs and stores in variables
        ├── Lines 97-99: Initializes global state:
        │   ├── currentChatHistory = []    ← Chat message history (empty)
        │   ├── sessionId = null           ← No session yet
        │   └── currentAbtController = null ← No active AI stream
        ├── Lines 103-122: Theme logic runs
        │   ├── Checks localStorage for saved theme preference
        │   ├── Applies 'light' or 'dark' data-theme attribute to <html>
        │   └── CSS variables change colors based on [data-theme]
        └── Lines 147-155: Attaches click listeners to all 6 tab buttons

Step 8: User sees the Upload Screen
        ├── #upload-screen has class "active" (visible)
        └── #dashboard-screen has class "hidden" (invisible)
```

**Result:** User sees the landing page with file upload form and "Generate Demo Data" button.

---

## FLOW 2: User Clicks "🎁 Generate Demo Data" (THE MAIN FLOW)

This is the most complex flow — it triggers 3 API calls and sets up the entire dashboard.

### Phase 1: Generate the CSV (script.js line 449-472)

```
Step 1: User clicks "Generate Demo Data"
        └── demoBtn click event fires (line 449)

Step 2: Show loading message
        uploadStatus.textContent = 'Generating 1,000 row TCS Synthetic Dataset...'
        (User sees green text below the buttons)

Step 3: Browser sends  GET /api/synthetic  to server
        fetch(`${API_BASE}/synthetic`)  → GET /api/synthetic
```

### Phase 2: Server generates synthetic data (main.py line 188-191, eda_engine.py line 375-399)

```
Step 4: FastAPI route @app.get("/api/synthetic") catches the request
        └── Calls create_synthetic_dataset() in eda_engine.py

Step 5: create_synthetic_dataset() runs:
        ├── np.random.seed(42)  → Makes data reproducible (same every time)
        ├── Creates a Polars DataFrame with 1000 rows:
        │   ├── Order_ID:         1001 to 2000 (sequential)
        │   ├── Product_Category: Random from ['Tech','Fashion','Home','Software']
        │   ├── Sales_Amount:     Random exponential distribution (scale=500)
        │   ├── Customer_Age:     Random integer 18-80
        │   ├── Marketing_Spend:  Random normal distribution (mean=100, std=30)
        │   ├── Smoker:           Random 'Yes' or 'No'
        │   ├── Region:           Random from ['North America','EMEA','APAC','LATAM']
        │   └── Satisfaction_Score: Random integer 1-5
        │
        ├── Modifies Sales_Amount: adds Marketing_Spend * 2.5
        │   (Creates a real correlation between these columns!)
        │
        ├── INTENTIONALLY injects dirty data:
        │   ├── Rows 0-10:   Sales_Amount = 99000.0  (OUTLIERS)
        │   └── Rows 50-150: Customer_Age = NaN       (MISSING VALUES)
        │
        └── Saves as uploads/tcs_demo_data.csv and returns the file path

Step 6: FastAPI returns FileResponse → Browser receives the CSV file as bytes
```

### Phase 3: Browser uploads the CSV right back (script.js line 458-467)

```
Step 7: Browser wraps the CSV bytes into a File object:
        const blob = await res.blob()  → Raw bytes
        const file = new File([blob], "tcs_demo_data.csv", { type: "text/csv" })
        WHY? The /api/upload endpoint expects a file upload (multipart form)

Step 8: Browser creates a FormData object:
        const formData = new FormData()
        formData.append('file', file)                    ← The CSV file
        formData.append('context', "This is a synthetic  ← Auto-generated context
          dataset for demo purposes...")

Step 9: Calls processUpload(formData) → the main upload function
```

### Phase 4: processUpload() — The Core Upload (script.js line 189-220)

```
Step 10: Shows loading status
         uploadStatus.textContent = 'Uploading and running Pandas profiling...'

Step 11: Browser sends  POST /api/upload  to server
         fetch(`${API_BASE}/upload`, { method: 'POST', body: formData })
         
         HTTP Request looks like:
         ┌─────────────────────────────────────────────┐
         │ POST /api/upload HTTP/1.1                    │
         │ Content-Type: multipart/form-data;           │
         │   boundary=----WebKitFormBoundary...         │
         │                                              │
         │ ------WebKitFormBoundary...                  │
         │ Content-Disposition: form-data; name="file"; │
         │   filename="tcs_demo_data.csv"               │
         │ Content-Type: text/csv                       │
         │                                              │
         │ Order_ID,Product_Category,Sales_Amount,...    │
         │ 1001,Tech,1484.23,45,120.50,Yes,APAC,3      │
         │ ...                                          │
         │ ------WebKitFormBoundary...                  │
         │ Content-Disposition: form-data; name="context│
         │                                              │
         │ This is a synthetic dataset...               │
         │ ------WebKitFormBoundary...--                │
         └─────────────────────────────────────────────┘
```

### Phase 5: Server processes the upload (main.py line 62-109)

```
Step 12: FastAPI parses the multipart form:
         file: UploadFile = File(...)  → The CSV file
         context: str = Form("")       → "This is a synthetic dataset..."

Step 13: Read file bytes into memory
         contents = await file.read()
         WHY await? File reading is async — doesn't block other requests

Step 14: Polars reads the CSV from bytes
         df = pl.read_csv(io.BytesIO(contents), ignore_errors=True)
         ├── io.BytesIO(contents) → Wraps raw bytes into a file-like object
         └── ignore_errors=True   → Skip malformed rows instead of crashing
         
         Result: Polars DataFrame with 1000 rows, 8 columns
         ┌──────────┬──────────────────┬──────────────┬──────────────┐
         │ Order_ID │ Product_Category │ Sales_Amount │ Customer_Age │
         │ i64      │ str              │ f64          │ f64          │
         ╞══════════╪══════════════════╪══════════════╪══════════════╡
         │ 1001     │ Software         │ 99000.0      │ 51.0         │
         │ 1002     │ Home             │ 99000.0      │ 75.0         │
         │ ...      │ ...              │ ...          │ ...          │
         └──────────┴──────────────────┴──────────────┴──────────────┘
```

### Phase 6: perform_analysis() (eda_engine.py line 46-112)

```
Step 15: Calculate statistics
         stats_df = df.describe()
         Returns count, null_count, mean, std, min, 25%, 50%, 75%, max
         for EACH column.
         
         Then reshapes from column-oriented to row-oriented format:
         Before: {statistic: 'mean', Sales_Amount: 2150.3, Age: 42.1}
         After:  {feature: 'Sales_Amount', mean: 2150.3, std: 8500.2, ...}

Step 16: Identify column types
         num_cols = ['Order_ID','Sales_Amount','Customer_Age',
                     'Marketing_Spend','Satisfaction_Score']  ← 5 numeric
         cat_cols = ['Product_Category','Smoker','Region']     ← 3 categorical

Step 17: Generate correlation heatmap
         ├── Convert ONLY numeric columns to Pandas: df.select(num_cols).to_pandas()
         ├── Calculate Pearson correlation: pd_num.corr()
         ├── Draw heatmap: sns.heatmap(corr, annot=True, cmap='coolwarm')
         ├── Save to BytesIO buffer as PNG
         ├── Base64-encode the PNG → "iVBORw0KGgoAAAA..."
         └── Close matplotlib figure (free memory!)

Step 18: Data quality audit
         Loop through every column:
         ├── Customer_Age: 101 nulls out of 1000 = 10.1% Null
         │   → Severity: "10.1% Null", Action: "Impute with Median/Mean"
         └── Sales_Amount: skewness = 6.2 (> 1.5 threshold)
             → Severity: "Skewness: 6.2", Action: "Log Transform/Cap"
         
         Result: audit_log = [
           {feature: 'Customer_Age', issue: 'Missing Values', severity: '10.1% Null', action: 'Impute with Median/Mean'},
           {feature: 'Sales_Amount', issue: 'High Skew', severity: 'Skewness: 6.2', action: 'Log Transform/Cap'}
         ]
```

### Phase 7: advanced_preprocessing() (eda_engine.py line 230-257)

```
Step 19: PII Scrubbing
         scrub_pii(df) checks:
         ├── Column names: None contain 'email','phone','ssn' → No masking
         └── Content: No column has >10% @ symbols → No masking
         Result: No PII detected

Step 20: Encoding detection
         ├── 'Smoker' has 2 unique values ['Yes','No'] → Binary Encoded: 'Yes'→0, 'No'→1
         ├── All 3 categorical columns → One-Hot Encoded: Product_Category, Smoker, Region
         └── Preview: pd.get_dummies(pd_df, drop_first=True) on top 5 rows
         
         encoding_log = [
           "Binary Encoded 'Smoker': 'Yes'→0, 'No'→1",
           "One-Hot Encoded: Product_Category, Smoker, Region"
         ]
```

### Phase 8: Save session & return response (main.py line 83-106)

```
Step 21: Generate session UUID
         session_id = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"

Step 22: Save to disk
         ├── sessions/a1b2c3d4-....json    ← Metadata (stats, audit, column types)
         └── sessions/a1b2c3d4-....parquet ← Data (compressed binary, 10x smaller than CSV)

Step 23: Return JSON response to browser:
         {
           "session_id": "a1b2c3d4-...",
           "audit": [{feature, issue, severity, action}, ...],
           "shape": [1000, 8],
           "correlation": "iVBORw0KGgoAAAA...",   ← Base64 heatmap image
           "encoding_log": ["Binary Encoded...", "One-Hot Encoded..."],
           "encoded_preview": [{Order_ID: 1001, Smoker_No: 1, ...}, ...],
           "num_cols": ["Order_ID", "Sales_Amount", ...],
           "cat_cols": ["Product_Category", "Smoker", "Region"]
         }
```

### Phase 9: populateDashboard() — Render everything (script.js line 222-365)

```
Step 24: Save session ID globally
         sessionId = data.session_id   ← Used by ALL subsequent API calls

Step 25: Populate Scorecard (3 boxes at top)
         ├── score-rows:    "1000"
         ├── score-missing: "1"   (1 column has missing values)
         │   └── Class set to 'warning' (orange) because missingCount > 0
         └── score-skew:    "1"   (1 column is highly skewed)
             └── Class set to 'danger' (red) because skewCount > 0

Step 26: Populate Audit Table
         For each audit item:
         ├── Determine badge color:
         │   ├── "10.1% Null" → parseFloat("10.1") > 0 → class="warning" (orange)
         │   └── "Skewness: 6.2" → split(':')[1] = 6.2 > 2 → class="danger" (red)
         └── Create table row: <tr><td>Customer_Age</td><td>Missing Values</td>...</tr>

Step 27: Populate Encoding Log
         encodingLogDiv.innerHTML = log items joined with <br> tags

Step 28: Populate Preview Table (ML-encoded view)
         ├── Get column names from first row → Create <th> headers
         └── For each of 5 rows → Create <tr> with <td> cells

Step 29: Populate ALL dropdown menus
         populateSelects(num_cols, cat_cols):
         ├── Transform column dropdown: All 8 columns
         ├── Scatter X/Y dropdowns: 5 numeric columns
         ├── Scatter Hue dropdown: 3 categorical + "None"
         ├── PCA Hue dropdown: 3 categorical + "None"
         ├── AutoML target dropdown: All 8 columns
         └── Spark dropdowns (8 selects): All 8 columns

Step 30: Setup Lazy Loading for Distribution Charts
         ├── Create IntersectionObserver with rootMargin: '100px'
         │   (Triggers loading when image is within 100px of viewport)
         │
         ├── For EACH of 8 columns:
         │   ├── Create <div class="visual-item">
         │   ├── Create <img> with:
         │   │   ├── dataset.col = "Sales_Amount"  (stored for later)
         │   │   ├── style: minHeight 250px, semi-transparent, no src yet
         │   │   └── alt = "Distribution of Sales_Amount"
         │   ├── observer.observe(img)  ← Watch this image
         │   └── Append to #visuals-grid
         │
         └── When user scrolls and image becomes visible:
             ├── IntersectionObserver fires callback
             ├── fetch(`/api/visual/${sessionId}/Sales_Amount`)
             │   └── Server generates matplotlib chart → returns Base64
             ├── img.src = "data:image/png;base64,iVBORw0KG..."
             ├── img.style.opacity = '1'  (fade-in effect)
             └── observer.unobserve(img)  (don't load again)

Step 31: Display correlation heatmap
         corrOutputDiv.innerHTML = `<img src="data:image/png;base64,${data.correlation}">`
```

### Phase 10: Switch screens & trigger AI (script.js line 206-214)

```
Step 32: Switch from Upload screen to Dashboard screen
         uploadScreen.classList.remove('active')  → hides it
         uploadScreen.classList.add('hidden')
         dashboardScreen.classList.remove('hidden')
         dashboardScreen.classList.add('active')   → shows it
         CSS: .hidden { display: none; }  .active { display: block; }

Step 33: Trigger AI report stream
         streamInitialReport()  → See FLOW 3 below

Step 34: Check PySpark availability
         checkSparkStatus()
         ├── GET /api/spark/status
         ├── Response: {"available": false}  (not installed on Render)
         └── Show warning banner: "⚠️ PySpark is not installed"
```

---

## FLOW 3: AI Report Streaming (script.js line 781-821)

```
Step 1: Create chat bubble
        chatHistory.innerHTML = '<div class="message ai-message">
          <i>Analyzing dataset...</i></div>'

Step 2: Create AbortController (for Stop button)
        currentAbtController = new AbortController()
        Show 🛑 Stop button

Step 3: Browser sends  GET /api/ai/report  with session-id header
        fetch(`/api/ai/report`, {
          headers: { 'session-id': sessionId },
          signal: currentAbtController.signal  ← Cancel if user clicks Stop
        })

Step 4: Server receives request (main.py line 127-144)
        ├── get_session() loads metadata + DataFrame from disk
        ├── Smart Context Chunking:
        │   Filter audit to only WARNING and DANGER items
        │   (Don't send "Clean" items to AI — waste of tokens)
        └── Return StreamingResponse(generate_initial_report(...))

Step 5: AI Engine builds the prompt (ai_engine.py line 35-68)
        system_prompt = """You are a Senior AI Engineer.
        Dataset: 1000 rows x 8 columns.
        Context: This is a synthetic dataset...
        Critical issues:
        [{"feature": "Customer_Age", "severity": "10.1% Null"},
         {"feature": "Sales_Amount", "severity": "Skewness: 6.2"}]
        Generate EDA Strategy Report covering:
        1. Data Quality Assessment
        2. Key Statistical Insights
        3. Feature Engineering steps
        4. ML approach"""

Step 6: Send to Groq API
        stream = await client.chat.completions.create(
          model="llama-3.3-70b-versatile",
          messages=[{system prompt}, {user message}],
          stream=True,           ← Word-by-word streaming
          temperature=0.7,       ← Balanced creativity
          max_tokens=2048        ← Maximum response length
        )

Step 7: Groq sends back tokens one at a time:
        chunk 1: "##"
        chunk 2: " Data"
        chunk 3: " Quality"
        chunk 4: " Assessment"
        chunk 5: "\n\n"
        chunk 6: "The"
        chunk 7: " dataset"
        ...

Step 8: FastAPI yields each chunk via StreamingResponse
        async for chunk in stream:
            yield chunk.choices[0].delta.content
        
        HTTP response is chunked:
        Transfer-Encoding: chunked
        Content-Type: text/event-stream

Step 9: Browser reads the stream (script.js line 794-807)
        const reader = response.body.getReader()   ← ReadableStream reader
        const decoder = new TextDecoder()           ← Bytes → String
        
        LOOP:
        ├── const {done, value} = await reader.read()  ← Wait for next chunk
        ├── reportText += decoder.decode(value)         ← Accumulate full text
        ├── reportDiv.innerHTML = renderMarkdown(text)  ← Re-render with markdown
        │   └── renderMarkdown() converts:
        │       ## Title       → <h2>Title</h2>
        │       **bold**       → <b>bold</b>
        │       *italic*       → <i>italic</i>
        │       \n             → <br>
        └── chatHistory.scrollTop = chatHistory.scrollHeight  ← Auto-scroll down

Step 10: When stream ends (done = true):
         ├── Save report to chat history:
         │   currentChatHistory.push({role: "assistant", content: fullText})
         └── Hide Stop button
```

---

## FLOW 4: User Sends a Chat Message

```
Step 1: User types "What columns have the most outliers?" and presses Enter
        ├── keypress event (line 881): e.key === 'Enter' → sendChatMessage()

Step 2: Create user message bubble (blue, right-aligned)
        userDiv.textContent = "What columns have the most outliers?"
        chatHistory.appendChild(userDiv)

Step 3: Create AI response bubble (dark, left-aligned)
        aiDiv.innerHTML = '<i>Thinking...</i>'
        chatHistory.appendChild(aiDiv)

Step 4: Browser sends  POST /api/ai/chat  with JSON body
        {
          "message": "What columns have the most outliers?",
          "history": [
            {"role": "assistant", "content": "## Data Quality Assessment\nThe dataset..."}
          ],
          "session_id": "a1b2c3d4-..."
        }

Step 5: Server builds context (ai_engine.py line 77-104)
        ├── Gets first 3 rows of data as a text table
        ├── Builds system prompt with column names, shape, sample data
        ├── Adds last 10 messages from history
        └── Appends user's question

Step 6: Groq streams response → FastAPI yields → Browser renders word-by-word
        (Same streaming mechanism as Flow 3)

Step 7: After stream completes:
        currentChatHistory.push({role: "user", content: question})
        currentChatHistory.push({role: "assistant", content: aiResponse})
        (History grows for future context)
```

---

## FLOW 5: User Applies a Transformation

```
Step 1: User selects "Sales_Amount" + "Log Transformation" → Clicks "Apply"

Step 2: Browser sends  POST /api/transform
        {"session_id": "...", "column": "Sales_Amount", "transform_type": "log"}

Step 3: Server processes (main.py line 208-242)
        ├── get_session() loads DataFrame from parquet
        ├── apply_custom_transformation(df, "Sales_Amount", "log")
        │   └── eda_engine.py line 313-318:
        │       min_val = df["Sales_Amount"].min()    → e.g., 5.2
        │       Since min_val > 0:
        │         df.with_columns(pl.col("Sales_Amount").map_elements(
        │           lambda x: np.log1p(x)))
        │       Before: [99000, 500, 1200, ...]
        │       After:  [11.50, 6.21, 7.09, ...]  ← Compressed range!
        │
        ├── Re-run full EDA: perform_analysis(df_trans)
        │   (New stats, new audit, new correlation — skewness should drop!)
        ├── Re-run preprocessing: advanced_preprocessing(df_trans)
        ├── Update session on disk (both .json and .parquet)
        └── Return same response format as upload

Step 4: Browser calls populateDashboard(data) AGAIN
        ├── Scorecard updates (skew count might drop to 0)
        ├── Audit table rebuilds (Sales_Amount skew entry might disappear)
        ├── Encoding log updates
        ├── Preview table rebuilds
        ├── ALL dropdowns re-populate
        └── Distribution charts re-setup with new IntersectionObservers
        
Step 5: User sees "✅ Successfully applied 'log' to 'Sales_Amount'"
        Message auto-clears after 5 seconds: setTimeout(() => {}, 5000)
```

---

## FLOW 6: Stop AI Button

```
Step 1: While AI is streaming, user clicks 🛑 Stop

Step 2: currentAbtController.abort()
        ├── This sends an AbortSignal to the fetch() call
        ├── fetch() throws AbortError
        └── catch block: err.name === 'AbortError'
            → Appends "[Stopped by User]" to the chat bubble

Step 3: Stream stops immediately — no more data from server
        Server-side: the generator function stops because the connection closes
```

---

## Summary: What Is Happening At Each Layer

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER (Browser)                          │
│  Clicks buttons → JS handles events → Calls fetch() APIs       │
│  Receives JSON/streams → Updates DOM → User sees results        │
├─────────────────────────────────────────────────────────────────┤
│                    NETWORK (HTTP/HTTPS)                          │
│  POST /api/upload (multipart) │ GET /api/visual/session/col     │
│  GET /api/ai/report (stream)  │ POST /api/ai/chat (stream)      │
│  POST /api/transform (JSON)   │ POST /api/chart (JSON)          │
├─────────────────────────────────────────────────────────────────┤
│                     FASTAPI (main.py)                            │
│  Routes → Validates → Calls engines → Returns responses         │
│  Session management (UUID → JSON + Parquet on disk)             │
├─────────────────────────────────────────────────────────────────┤
│                    EDA ENGINE (eda_engine.py)                    │
│  Polars: stats, audit, transforms, PCA, cleaning                │
│  Pandas: ONLY for matplotlib/seaborn chart rendering            │
│  NumPy: Math operations, random data, log/sqrt                  │
├─────────────────────────────────────────────────────────────────┤
│                    AI ENGINE (ai_engine.py)                      │
│  Builds prompts → Sends to Groq API → Yields streamed tokens   │
├─────────────────────────────────────────────────────────────────┤
│                    GROQ CLOUD (External)                        │
│  Llama 3.3 70B model → Generates text word-by-word              │
├─────────────────────────────────────────────────────────────────┤
│                    DOCKER CONTAINER                              │
│  Packages everything → Runs on Render → Accessible via URL      │
└─────────────────────────────────────────────────────────────────┘
```
