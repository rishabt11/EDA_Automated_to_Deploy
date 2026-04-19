# Code Documentation

This document explains the architecture and logic of the platform section by section.

## 1. `backend/main.py` (FastAPI Router)
This is the entry point for the backend.
- **Imports & Setup:** Initializes FastAPI, sets up CORS (Cross-Origin Resource Sharing) to allow frontend requests, and ensures the `/sessions/` directory exists for file storage.
- **Session Management (`is_valid_uuid`, `get_session`, `save_session`):** Prevents path traversal vulnerabilities by enforcing strict UUID regex formatting. Reads and writes DataFrames as `.parquet` files for scalability.
- **`/api/upload` (POST):** Receives the CSV/XLSX file. Generates a new `session_id`, reads the file into a Polars DataFrame, runs the EDA audit, and returns the metadata to the frontend.
- **`/api/transform` (POST):** Accepts a target column and transformation type (e.g., `log`, `minmax_scale`). It calls the Polars engine to apply the math, re-runs the EDA audit, and saves the updated DataFrame back to disk.
- **`/api/visual/{session_id}/{column}` (GET):** Generates a base64 encoded PNG of the data distribution for a specific column using Seaborn. This powers the lazy-loading frontend.
- **`/api/automl` (POST):** Generates a dynamic Python string containing `scikit-learn` code tailored to the dataset's target column and returns it as a downloadable `.py` file.

## 2. `backend/eda_engine.py` (Polars Data Processing)
Handles all heavy data lifting using Rust-based Polars.
- **`scrub_pii(df)`:** Uses regex and string matching to find columns containing emails or PII keywords (SSN, credit card). Replaces values with `[REDACTED]` to prevent leaking data to the LLM.
- **`perform_analysis(df)`:** Calculates null counts, unique counts, and skewness across the dataset. Generates the `audit` list (identifying "Dangers" and "Warnings").
- **`advanced_preprocessing(df)`:** Runs the PII scrubber and prepares a small 5-row preview table for the frontend.
- **`apply_custom_transformation(df, column, transform_type)`:** A massive switch-case using Polars Expressions (`pl.col()`) to apply math operations. For example, `binning_5` uses `cut()` to group data, and `cap_outliers_iqr` calculates quantiles and uses `clip()`.
- **`generate_single_distribution(df, column)`:** Drops nulls, converts the Polars column to a pandas Series, plots it with Seaborn/Matplotlib, and encodes it to base64.

## 3. `backend/ai_engine.py` (LLM Integration)
Handles communication with LM Studio (OpenAI-compatible server).
- **`generate_initial_report(...)`:** Compiles the user's business context, the dataset shape, and *only* the critical audit warnings into a system prompt. Streams the response using `AsyncOpenAI`.
- **`chat_with_data(...)`:** Takes the ongoing chat history from the frontend, injects the dataset context into the system prompt, and streams the AI's reply back to the user.

## 4. `frontend/script.js` (Client-Side Logic)
Controls the UI and API fetching.
- **Theme Logic:** Checks `localStorage` to toggle `[data-theme="light/dark"]` on the root element.
- **Upload Logic:** Sends `FormData` to `/api/upload`. On success, it unhides the dashboard and populates the tables.
- **Lazy Loading (`IntersectionObserver`):** Watches the empty `div` containers in the Visuals tab. When they enter the viewport, it fetches the `/api/visual/...` image and inserts it, saving massive amounts of bandwidth.
- **AI Streaming & AbortController:** Uses `fetch` and a `TextDecoder` to read chunks from the FastAPI streaming endpoint. Passes an `AbortController.signal` so the user can instantly sever the HTTP connection using the "Stop" button.
- **HTML Sanitization (`escapeHTML`):** Prevents Cross-Site Scripting (XSS) by replacing `<` and `>` with HTML entities before rendering the AI's markdown.

## 5. `frontend/index.html` & `frontend/style.css`
- **Glassmorphism Design:** Uses `backdrop-filter: blur(16px)` and CSS custom properties (variables) to create a premium UI.
- **Flexbox & Grid Layouts:** Ensures the dashboard scales cleanly across screen sizes.
- **Print Media Query (`@media print`):** A special CSS block that strips away buttons and dark backgrounds so the page prints perfectly as a PDF report.

## 6. `backend/spark_engine.py` (PySpark Processing Engine)
A complete PySpark engine organized into the 10 standard PySpark function categories:

### 🔹 1. Basic Setup
- **`get_spark()`:** Creates/returns the active `SparkSession` with `local[*]` master (uses all CPU cores). Configures 4GB driver memory and Arrow optimization.
- **`load_csv(filepath)`:** Reads CSV with `header=True` and `inferSchema=True`.
- **`get_schema_info(sdf)`:** Returns schema as a list of dicts (column, type, nullable).
- **`get_preview(sdf, n)`:** Returns first `n` rows as dicts (equivalent to `show()`).

### 🔹 2. Filtering & Cleaning
- **`filter_rows(sdf, column, operator, value)`:** Implements `filter()`/`where()` with all 6 comparison operators.
- **`drop_nulls(sdf, subset)`:** Wraps `dropna()` with optional column subset.
- **`fill_nulls(sdf, column, strategy)`:** Implements `fillna()` with mean/median/mode/zero strategies.
- **`replace_values(sdf, column, old, new)`:** Maps specific values using `when().otherwise()`.
- **`drop_duplicates(sdf, subset)`:** Wraps `dropDuplicates()`.

### 🔹 3. Column Operations
- **`add_or_modify_column(sdf, column, expression)`:** Implements `withColumn()` for log, sqrt, square, abs, reciprocal.
- **`drop_column()`, `rename_column()`, `cast_column()`:** Wrap `drop()`, `alias()`, `cast()`.
- **`conditional_column()`:** Implements `when().otherwise()` for if-else column logic.

### 🔹 4. Aggregation & Grouping
- **`group_and_aggregate(sdf, group_cols, agg_dict)`:** Implements `groupBy().agg()` supporting sum, avg, count, min, max, stddev.

### 🔹 5. Sorting
- **`sort_data(sdf, column, ascending)`:** Implements `orderBy()` with ascending/descending support.

### 🔹 6. Joins
- **`join_dataframes(sdf1, sdf2, on_column, how)`:** Implements `join()` with all join types (inner, left, right, outer, cross, semi, anti).

### 🔹 7. Window Functions
- **`add_row_number()`:** `row_number()` over `Window.partitionBy().orderBy()`.
- **`add_rank()`:** `rank()` and `dense_rank()` within partitions.
- **`add_lag_lead()`:** `lag()` and `lead()` for time-series analysis.
- **`add_running_total()`:** Cumulative sum using `rowsBetween(unboundedPreceding, currentRow)`.

### 🔹 8. UDFs
- **`apply_udf_example()`:** Demonstrates built-in string UDFs (upper, lower, length, reverse) without requiring custom user code.

### 🔹 9. Saving Data
- **`save_as_csv()` / `save_as_parquet()`:** Implements `write.csv()` and `write.parquet()` with mode control.

### 🔹 10. Descriptive Stats
- **`describe_data()`:** Wraps `describe()` for count, mean, stddev, min, max.
- **`summary_data()`:** Wraps `summary()` for extended metrics including percentiles.

### Bonus: Full Analysis Pipeline
- **`spark_perform_analysis(sdf)`:** Mirrors the Polars `perform_analysis()` function. Runs a full EDA audit (nulls, skewness, constants) using Spark SQL functions.
- **`spark_apply_transformation(sdf, column, type)`:** Mirrors `apply_custom_transformation()` using PySpark expressions (`F.log1p`, `F.sqrt`, `F.pow`, etc.).

