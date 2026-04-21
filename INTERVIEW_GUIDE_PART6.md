# EDA Automated (Deploy) — Interview Guide Part 6: Everything That Was Missing

---

## 1. `backend/spark_engine.py` — The PySpark Engine (554 lines)

This file is a **complete PySpark processing engine** — it mirrors the Polars engine but uses Apache Spark for distributed computing.

> **CRITICAL:** PySpark is NOT installed on Render (free tier can't handle a JVM). This entire file is lazy-imported with try/except in main.py. If PySpark isn't available, the Spark tab shows a warning and all Spark endpoints return errors gracefully.

---

### Section 1: SparkSession Setup (Lines 28-41)

```python
def get_spark():
    spark = SparkSession.builder \
        .appName("DataEngineerPro") \
        .master("local[*]") \
        .config("spark.driver.memory", "4g") \
        .config("spark.sql.execution.arrow.pyspark.enabled", "true") \
        .getOrCreate()
    spark.sparkContext.setLogLevel("WARN")
    return spark
```

**Q: "What is a SparkSession?"**
> "SparkSession is the single entry point to all Spark functionality. Think of it as the 'connection' to the Spark engine. `.builder` creates a builder pattern, `.getOrCreate()` reuses an existing session or creates a new one."

**Q: "What does `master('local[*]')` mean?"**
> "It tells Spark to run in **local mode** using ALL available CPU cores. `[*]` = all cores. `[2]` would mean only 2 cores. In a real cluster, you'd use `spark://master:7077` to connect to a Spark cluster."

**Q: "What does `arrow.pyspark.enabled=true` do?"**
> "Apache Arrow is a columnar memory format. When enabled, Spark uses Arrow to convert between Spark DataFrames and Pandas DataFrames — this makes `.toPandas()` up to **100x faster** by avoiding row-by-row serialization."

**Q: "Why `setLogLevel('WARN')`?"**
> "By default, Spark logs EVERYTHING (DEBUG level) — thousands of lines per operation. WARN level only shows warnings and errors, keeping the console clean."

---

### Section 2: Data Loading (Lines 44-57)

```python
def load_csv(filepath):
    spark = get_spark()
    return spark.read.csv(filepath, header=True, inferSchema=True)
```

- `header=True` → First row = column names (not data)
- `inferSchema=True` → Spark automatically detects types (int, double, string). Without this, ALL columns are StringType.

```python
def load_parquet(filepath):
    return spark.read.parquet(filepath)
```

**Q: "Why support both CSV and Parquet?"**
> "User uploads CSV. But internally we store as Parquet (faster, smaller). When the Spark tab loads data, it reads the session's Parquet file."

---

### Section 3: Filtering & Cleaning (Lines 85-153)

```python
def filter_rows(sdf, column, operator, value):
    col = F.col(column)
    if operator == ">":    return sdf.filter(col > value)
    elif operator == "<":  return sdf.filter(col < value)
    elif operator == ">=": return sdf.filter(col >= value)
    elif operator == "==": return sdf.filter(col == value)
    ...
```

**Q: "What is `F.col(column)`?"**
> "`F` is `pyspark.sql.functions`. `F.col("Sales")` creates a Column object — it's like saying 'the Sales column.' You can then apply operators: `F.col("Sales") > 1000` creates a filter condition."

```python
def fill_nulls(sdf, column, strategy="mean"):
    if strategy == "mean":
        mean_val = sdf.select(F.mean(column)).collect()[0][0]
        return sdf.fillna({column: mean_val})
    elif strategy == "median":
        median_val = sdf.approxQuantile(column, [0.5], 0.01)[0]
        return sdf.fillna({column: median_val})
    elif strategy == "mode":
        mode_val = sdf.groupBy(column).count().orderBy(F.desc("count")).first()[0]
        return sdf.fillna({column: mode_val})
```

**Q: "Why `approxQuantile` for median instead of exact?"**
> "Exact median requires sorting ALL data — O(n log n). `approxQuantile` uses the Greenwald-Khanna algorithm — O(n) with 1% error tolerance (the `0.01` parameter). For 10M rows, exact takes 30 seconds, approximate takes 2 seconds."

**Q: "How does mode work here?"**
> "Group by the column value, count occurrences, sort descending, take the first row. Example: if 'Tech' appears 300 times and 'Home' appears 200 times, `first()[0]` returns 'Tech'."

---

### Section 4: Column Operations (Lines 160-229)

```python
def add_or_modify_column(sdf, column, expression):
    if expression == "log":
        return sdf.withColumn(column, F.log1p(F.col(column)))
    elif expression == "sqrt":
        return sdf.withColumn(column, F.sqrt(F.abs(F.col(column))))
    elif expression == "reciprocal":
        return sdf.withColumn(column,
            F.when(F.col(column) != 0, 1.0 / F.col(column)).otherwise(None))
```

**Q: "What is `withColumn()`?"**
> "It creates a NEW DataFrame with a column added or replaced. Spark DataFrames are **immutable** — you can't modify them in-place. `withColumn("Sales", F.log1p(F.col("Sales")))` returns a new DataFrame where the Sales column is log-transformed."

**Q: "What is `F.when().otherwise()`?"**
> "Spark's version of if-else. `F.when(condition, value).otherwise(other_value)`. For reciprocal: if value ≠ 0, return 1/x; otherwise return null (to avoid division by zero)."

```python
def cast_column(sdf, column, new_type):
    type_map = {
        "int": IntegerType(),
        "float": FloatType(),
        "double": DoubleType(),
        "string": StringType(),
        "boolean": BooleanType(),
    }
    return sdf.withColumn(column, F.col(column).cast(target))
```

**Q: "What is `cast()`?"**
> "Type conversion. Like Python's `int('42')`. In Spark: `F.col("Age").cast(IntegerType())` converts string '42' to integer 42."

---

### Section 5: GroupBy & Aggregation (Lines 236-263)

```python
def group_and_aggregate(sdf, group_cols, agg_dict):
    agg_exprs = []
    for col_name, op in agg_dict.items():
        if op == "sum":    agg_exprs.append(F.sum(col_name).alias(f"{col_name}_sum"))
        elif op == "avg":  agg_exprs.append(F.avg(col_name).alias(f"{col_name}_avg"))
        elif op == "count":agg_exprs.append(F.count(col_name).alias(f"{col_name}_count"))
        ...
    return sdf.groupBy(*group_cols).agg(*agg_exprs)
```

**Q: "Walk through a GroupBy example."**
> Input: `group_cols=["Region"]`, `agg_dict={"Sales_Amount": "sum"}`
>
> Step 1: `groupBy("Region")` — groups rows by Region (North America, EMEA, APAC, LATAM)
> Step 2: `agg(F.sum("Sales_Amount").alias("Sales_Amount_sum"))` — sums Sales for each group
> Result:
> | Region | Sales_Amount_sum |
> |--------|-----------------|
> | APAC | 125000.50 |
> | EMEA | 98000.25 |

**Q: "What does `.alias()` do?"**
> "Renames the output column. Without it, the column would be named `sum(Sales_Amount)` — ugly and hard to reference in code."

---

### Section 6: Window Functions (Lines 296-338) — THE INTERVIEW GOLD

```python
def add_row_number(sdf, partition_col, order_col):
    window_spec = Window.partitionBy(partition_col).orderBy(order_col)
    return sdf.withColumn("row_number", F.row_number().over(window_spec))
```

**Q: "Explain window functions like I'm 5."**
> "Imagine a class of students sorted by marks. `rank()` gives each student a position — 1st, 2nd, 3rd. But if two students tie at 2nd place, `rank()` gives both 2nd and skips 3rd (next is 4th). `dense_rank()` gives both 2nd and the next student gets 3rd (no gap). `row_number()` gives UNIQUE numbers even for ties."

> | Student | Marks | rank() | dense_rank() | row_number() |
> |---------|-------|--------|-------------|-------------|
> | Alice | 95 | 1 | 1 | 1 |
> | Bob | 90 | 2 | 2 | 2 |
> | Charlie | 90 | 2 | 2 | 3 |
> | Diana | 85 | 4 | 3 | 4 |

```python
def add_lag_lead(sdf, partition_col, order_col, target_col, offset=1, func="lag"):
    window_spec = Window.partitionBy(partition_col).orderBy(order_col)
    if func == "lag":
        return sdf.withColumn(f"{target_col}_lag_{offset}",
            F.lag(target_col, offset).over(window_spec))
    elif func == "lead":
        return sdf.withColumn(f"{target_col}_lead_{offset}",
            F.lead(target_col, offset).over(window_spec))
```

**Q: "What are lag and lead?"**
> "`lag(col, 1)` = look at the PREVIOUS row's value. `lead(col, 1)` = look at the NEXT row's value. Used for time-series: 'What was last month's sales?' (lag) or 'What will next month's sales be?' (lead)."

```python
def add_running_total(sdf, partition_col, order_col, sum_col):
    window_spec = Window.partitionBy(partition_col).orderBy(order_col) \
        .rowsBetween(Window.unboundedPreceding, Window.currentRow)
    return sdf.withColumn(f"{sum_col}_cumsum", F.sum(sum_col).over(window_spec))
```

**Q: "What is `rowsBetween(unboundedPreceding, currentRow)`?"**
> "It defines the window frame — which rows to include in the calculation. `unboundedPreceding` = from the very first row. `currentRow` = up to this row. So it sums ALL rows from the start up to the current row = **running total (cumulative sum)**."

---

### Section 7: Full Spark EDA (Lines 414-486)

```python
def spark_perform_analysis(sdf):
    num_cols = [f.name for f in sdf.schema.fields
                if isinstance(f.dataType, (IntegerType, DoubleType, FloatType))]
```

**Q: "How does Spark detect column types?"**
> "Spark DataFrames have a `schema` property with typed `fields`. Each field has a `dataType` — we check if it's numeric (Int/Double/Float) or categorical (String/Boolean). This is equivalent to Polars' `pl.NUMERIC_DTYPES`."

This function mirrors the Polars `perform_analysis()` — it calculates nulls, skewness, unique counts, and generates an audit. The output format is IDENTICAL so the frontend doesn't need to know which engine generated it.

---

## 2. `frontend/style.css` — Complete Design System (447 lines)

### CSS Variables — The Theme Engine (Lines 1-41)

```css
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap');
```
**Q: "What does this line do?"**
> "Downloads the 'Outfit' font from Google Fonts. It's a modern geometric sans-serif font. The `wght@300;400;500;600;700` loads 5 font weights so we can use thin (300) to bold (700)."

```css
:root, [data-theme="dark"] {
    --bg-gradient: linear-gradient(135deg, #090912 0%, #171128 100%);
    --glass-bg: rgba(30, 30, 45, 0.6);
    --text-main: #f8fafc;
    --accent: #6366f1;        /* Indigo — the primary brand color */
    --danger: #f43f5e;        /* Rose red — errors & high severity */
    --warning: #f59e0b;       /* Amber — medium severity */
    --success: #10b981;       /* Emerald — good status */
}
```

**Q: "What are CSS variables and why use them?"**
> "CSS variables (custom properties) let you define values ONCE and reuse them everywhere. `var(--accent)` is used in 20+ places. To change the brand color from indigo to blue, you change ONE line instead of 20."

**Q: "How does dark/light mode work?"**
> "JavaScript sets `data-theme='light'` on the `<html>` element. CSS has TWO blocks of variables: one for `[data-theme='dark']` and one for `[data-theme='light']`. When the attribute changes, ALL colors update instantly because every element uses `var(--text-main)` instead of hardcoded colors."

### Animation System (Lines 224, 296)

```css
@keyframes fadeIn {
    from { opacity: 0; transform: translateY(5px); }
    to   { opacity: 1; transform: translateY(0); }
}

@keyframes slideIn {
    from { opacity: 0; transform: translateX(10px); }
    to   { opacity: 1; transform: translateX(0); }
}
```

- `fadeIn` — Used on tab panes. When you switch tabs, the new content fades in from slightly below.
- `slideIn` — Used on chat messages. New messages slide in from the right.

### Button Micro-Animations (Lines 118-138)

```css
button {
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);  /* Smooth easing */
}
button:hover {
    transform: translateY(-1px);          /* Float up 1px */
    box-shadow: 0 4px 12px var(--accent-glow);  /* Glow effect */
}
button:active {
    transform: translateY(1px);           /* Push down 1px */
}
```

**Q: "What is `cubic-bezier(0.4, 0, 0.2, 1)`?"**
> "It's a custom easing curve — how the animation accelerates and decelerates. This specific curve is Google Material Design's 'standard easing.' It starts slow, speeds up, then slows down at the end. Much more natural than `linear` or `ease`."

### Print/PDF Styles (Lines 311-335)

```css
@media print {
    body { background: white !important; }
    .glass-panel, .card { background: white !important; color: black !important; }
    header button, .tabs, .resizer { display: none !important; }
    .dashboard-layout { display: block !important; }
    .tab-pane { display: block !important; page-break-after: always; }
}
```

**Q: "How does PDF export work?"**
> "When the user clicks 'Export Report', JavaScript calls `window.print()`. The `@media print` CSS kicks in — it removes all dark mode styling, hides interactive elements (buttons, tabs, resizer), and shows ALL tab panes at once (normally only the active one is visible). Each tab gets `page-break-after: always` so they start on new pages."

### Mobile Responsive (Lines 342-445) — 3 Breakpoints

| Breakpoint | Target | Key Changes |
|---|---|---|
| `≤768px` | Tablets | Stack panels vertically, hide resizer, scrollable tabs |
| `≤480px` | Phones | Smaller fonts, compact padding, 95% width messages |
| `print` | PDF | White bg, no buttons, all tabs visible |

---

## 3. `script.js` Helper Functions

### `escapeHTML()` — XSS Protection (Line 124)
```javascript
function escapeHTML(str) {
    return str
        .replace(/&/g, "&amp;")    // & → &amp;
        .replace(/</g, "&lt;")     // < → &lt;
        .replace(/>/g, "&gt;")     // > → &gt;
        .replace(/"/g, "&quot;")   // " → &quot;
        .replace(/'/g, "&#039;");  // ' → &#039;
}
```

**Q: "What is XSS and why escape HTML?"**
> "Cross-Site Scripting. If a user names a CSV column `<script>alert('hacked')</script>`, and we display it with `innerHTML`, the browser would execute that JavaScript. `escapeHTML` converts `<` to `&lt;` so the browser shows the text literally instead of executing it."

### `renderMarkdown()` — AI Text Formatting (Line 134)
```javascript
function renderMarkdown(text) {
    let html = safeText
        .replace(/^### (.*$)/gim, '<h3>$1</h3>')    // ### Title → <h3>
        .replace(/\*\*(.*)\*\*/gim, '<b>$1</b>')     // **bold** → <b>
        .replace(/\*(.*)\*/gim, '<i>$1</i>')          // *italic* → <i>
        .replace(/\n/gim, '<br>');                     // newline → <br>
}
```

> "This is a minimal markdown parser. The AI returns text with `**bold**` and `### headings`. This function converts them to HTML for display. It's NOT a full parser (no lists, links, code blocks) — just enough for readable AI responses."

### `renderSparkTable()` — Dynamic Table Builder (Line 599)
```javascript
function renderSparkTable(rows) {
    const cols = Object.keys(rows[0]);    // Get column names from first row
    let html = '<table><thead><tr>';
    cols.forEach(c => html += `<th>${c}</th>`);  // Header row
    html += '</tr></thead><tbody>';
    rows.forEach(row => {                         // Data rows
        html += '<tr>';
        cols.forEach(c => html += `<td>${row[c] !== null ? row[c] : 'null'}</td>`);
        html += '</tr>';
    });
    return html;
}
```

> "Takes an array of objects (JSON from the Spark API) and builds an HTML table dynamically. Handles null values by displaying the string 'null'."

### Theme Persistence via localStorage (Line 103)
```javascript
let isLightMode = localStorage.getItem('theme') === 'light';  // Read saved preference
// ...
localStorage.setItem('theme', isLightMode ? 'light' : 'dark'); // Save on toggle
```

**Q: "What is localStorage?"**
> "Browser storage that persists across page reloads and browser restarts. Unlike cookies, it's never sent to the server. We use it to remember the user's dark/light mode preference. Maximum 5MB per domain."

---

## 4. `requirements.txt` — Every Dependency Explained

```
fastapi>=0.104.0          # Web framework — handles all HTTP routes
uvicorn>=0.24.0           # ASGI server — runs FastAPI (handles TCP connections)
python-multipart>=0.0.6   # Parses multipart/form-data (file uploads!)
polars>=0.20.0            # Primary data engine (Rust-based, 10x faster than Pandas)
pandas>=2.1.0             # Used ONLY for chart rendering (matplotlib needs it)
numpy>=1.26.0             # Math operations (log, sqrt, random data generation)
matplotlib>=3.8.0         # Chart rendering engine (saves PNG to memory)
seaborn>=0.13.0           # Statistical plots on top of matplotlib (heatmaps, etc.)
scikit-learn>=1.3.0       # PCA + StandardScaler + ML script generation
openai>=1.6.0             # OpenAI-compatible client (for LM Studio local mode)
groq>=0.4.0               # Groq cloud AI client (Llama 3.3 70B)
pyarrow>=14.0.0           # Bridge between Polars and Pandas (.to_pandas())
python-dotenv>=1.0.0      # Reads .env files for local development
```

**Q: "Why `python-multipart`?"**
> "FastAPI can't parse file uploads without it. When the browser sends a `multipart/form-data` POST, this library extracts the file bytes and form fields. Without it, `UploadFile = File(...)` throws a runtime error."

**Q: "Why `pyarrow`?"**
> "Polars stores data in Arrow format internally. When we call `df.to_pandas()`, Polars uses PyArrow to convert Arrow arrays to Pandas arrays. Without PyArrow, `.to_pandas()` crashes with `ModuleNotFoundError`."

**Q: "What does `>=0.104.0` mean?"**
> "Install version 0.104.0 or higher. This ensures we get bug fixes and features added after 0.104.0, but doesn't lock to an exact version. For production, you'd use `==0.104.0` (exact pin) for reproducibility."

---

## 5. `eda_engine_pandas.py` — The Legacy Backup (289 lines)

**Q: "Why is this file in the project?"**

> "This is the ORIGINAL engine from before we migrated to Polars. It does everything using pure Pandas — `perform_analysis()`, `generate_visualizations()`, `advanced_preprocessing()`, `auto_clean_dataset()`, `apply_custom_transformation()`, and `create_synthetic_dataset()`. It's kept as a fallback — if Polars ever breaks in production, we can swap back by changing ONE import line in `main.py`. It's NOT imported or used anywhere in the current codebase."

**Key difference from the Polars engine:**

| Feature | Pandas (`eda_engine_pandas.py`) | Polars (`eda_engine.py`) |
|---|---|---|
| Stats | `df.describe(include='all').transpose()` | `df.describe()` + manual reshape |
| Null check | `df[col].isnull().sum()` | `df[col].null_count()` |
| Skewness | `df[col].skew()` | `pl.col(col).skew()` |
| Correlation | `df[num_cols].corr()` | `df.select(num_cols).to_pandas().corr()` |
| Visuals | Generates ALL charts at once (slow!) | Lazy-loads one chart at a time (fast!) |
| Speed | ~5 seconds for 1M rows | ~200ms for 1M rows |

**Q: "Why didn't you delete it?"**
> "Three reasons: (1) It serves as documentation of the migration path — shows what changed and why. (2) It's a safety net — one import change restores the old behavior. (3) In an interview, it demonstrates I understand BOTH Pandas AND Polars, and can articulate why I migrated."

---

## 6. `.env.example` — Environment Variable Template

```bash
# AI Provider: "groq" or "lmstudio"
AI_PROVIDER=groq

# Groq API Key (get free at https://console.groq.com)
GROQ_API_KEY=gsk_your_key_here

# LM Studio (only for local development)
LMSTUDIO_URL=http://127.0.0.1:1234/v1

# Server
PORT=8080
```

**Q: "Why `.env.example` and not `.env`?"**
> "`.env` contains REAL secrets (your actual API key) — it's in `.gitignore` and NEVER committed. `.env.example` contains PLACEHOLDER values — it's committed to show other developers what variables they need to set. A new developer clones the repo, copies `.env.example` to `.env`, and fills in their own keys."

---

## ✅ Coverage Complete — Nothing Left Unexplained

| Part | Files Covered |
|---|---|
| Part 1 | Architecture, tech stack, sessions, CORS, API list |
| Part 2 | `main.py`, `ai_engine.py` |
| Part 3 | `eda_engine.py` |
| Part 4 | `Dockerfile`, `.dockerignore`, `.gitignore`, HTML, CSS basics, Render |
| Part 5 | 6 complete end-to-end flows |
| **Part 6** | **`spark_engine.py`, `style.css` full, `script.js` helpers, `requirements.txt`, `eda_engine_pandas.py`, `.env.example`** |
