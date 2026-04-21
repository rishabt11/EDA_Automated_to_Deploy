# EDA Automated (Deploy) — Interview Guide Part 3: EDA Engine Line-by-Line

---

## File: `backend/eda_engine.py` — The Data Analysis Kitchen (400 lines)

This file does ALL the data processing: statistics, charts, PII detection, transformations, PCA, and dataset cleaning.

---

## Lines 1-11: Imports

```python
import polars as pl           # Primary data engine (fast!)
import pandas as pd           # Used ONLY for chart rendering (matplotlib needs it)
import numpy as np            # Math operations (random, log, sqrt)
import matplotlib             
matplotlib.use('Agg')         # ← CRITICAL: Use non-interactive backend
import matplotlib.pyplot as plt
import seaborn as sns          # Statistical visualization library
import io                     # In-memory file streams
import base64                 # Encode PNG images as text strings
import uuid                   # Generate unique filenames
import os
```

### Q: "What does `matplotlib.use('Agg')` do?"

> "Matplotlib normally tries to open a GUI window to display charts. On a cloud server (Docker/Render), there IS no screen. The 'Agg' backend tells matplotlib to render charts to memory (PNG bytes) instead of trying to open a window. Without this line, the app crashes with 'no display available'."

### Q: "Why import both Polars AND Pandas?"

> "Polars is the primary engine — all data loading, storage, and transformations use Polars. But Matplotlib/Seaborn only accept Pandas DataFrames. So when generating charts, we convert just the needed columns to Pandas at the last moment. Think of it as: Polars = the engine, Pandas = the translator for the charting library."

---

## Lines 13-43: PII Scrubbing

```python
def scrub_pii(df: pl.DataFrame):
    """Detects and masks PII in string columns."""
    str_cols = df.select(pl.col(pl.String)).columns
```

**What is PII?** Personally Identifiable Information — names, emails, phone numbers, SSNs, credit card numbers.

**How does detection work? (Two strategies)**

**Strategy 1 — Column name matching:**
```python
if any(kw in c_lower for kw in ['email', 'phone', 'ssn', 'credit', 'card', 'name', 'ip_address']):
    exprs.append(pl.lit("[REDACTED]").alias(col))
```
If the column is NAMED "email" or "phone", mask the entire column. This catches 90% of PII.

**Strategy 2 — Content pattern detection:**
```python
email_count = df.select(pl.col(col).str.contains("@")).sum()[0, 0]
if email_count and email_count > (df.height * 0.1):
    exprs.append(pl.lit("[REDACTED_EMAIL]").alias(col))
```
Even if the column isn't named "email", if >10% of values contain `@`, it's probably emails. Mask it.

**Q: "What does `pl.lit("[REDACTED]").alias(col)` mean?"**
> `pl.lit("[REDACTED]")` creates a column where EVERY row has the value "[REDACTED]". `.alias(col)` names it the same as the original column. When used in `with_columns()`, it replaces the original column entirely.

**Q: "Is this GDPR-compliant?"**
> "It's a basic implementation. For full GDPR compliance, you'd need regex patterns for specific formats (phone numbers by country, national IDs), named entity recognition (NLP-based detection), and data retention policies. This catches the obvious cases for a portfolio project."

---

## Lines 46-112: Core EDA Analysis (`perform_analysis`)

```python
def perform_analysis(df: pl.DataFrame):
```

This is the **most important function** in the entire codebase. Every upload calls this.

### Step 1: Descriptive Statistics
```python
stats_df = df.describe()
```
Returns a DataFrame with count, null_count, mean, std, min, 25%, 50%, 75%, max for each column.

```python
cols = [col for col in stats_df.columns if col != 'statistic']
for col in cols:
    col_stats = {"feature": col}
    for i, row in enumerate(stats_df.iter_rows(named=True)):
        stat_name = row['statistic']
        col_stats[stat_name] = row[col]
    stats_list.append(col_stats)
```

**Q: "Why this complex reshaping?"**
> "Polars `describe()` returns stats as ROWS and columns as COLUMNS — the opposite of what the frontend expects. The frontend wants each COLUMN to be a row with stats. So we transpose the data manually. Example:
>
> Polars returns: `{statistic: 'mean', Sales: 500, Age: 35}`
> We need: `{feature: 'Sales', mean: 500, std: 200, ...}`"

### Step 2: Identify Column Types
```python
num_cols = df.select(pl.col(pl.NUMERIC_DTYPES)).columns
cat_cols = [col for col in df.columns if col not in num_cols]
```

**Q: "What is `pl.NUMERIC_DTYPES`?"**
> It's a Polars constant that includes `Int8, Int16, Int32, Int64, Float32, Float64, UInt8, UInt16, UInt32, UInt64`. Any column with one of these types is "numeric." Everything else is "categorical."

### Step 3: Correlation Heatmap
```python
if len(num_cols) > 1:
    pd_num = df.select(num_cols).to_pandas()   # Convert ONLY numeric cols to Pandas
    corr = pd_num.corr()                        # Pearson correlation matrix
    plt.figure(figsize=(8, 6))
    sns.heatmap(corr, annot=True, cmap='coolwarm', center=0)
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    plt.close()
    corr_html_str = base64.b64encode(buf.getvalue()).decode("utf-8")
```

**Q: "Walk me through the image generation pipeline."**
> 1. Create a matplotlib figure in memory
> 2. Use Seaborn to draw a heatmap on it
> 3. Save the figure to a BytesIO buffer (in-memory file) as PNG
> 4. Close the figure (free memory!)
> 5. Base64-encode the PNG bytes → becomes a long text string like `iVBORw0KGgoAAAA...`
> 6. Send this string to the browser
> 7. Browser displays it as: `<img src="data:image/png;base64,iVBORw0KGgoAAAA...">`

**Q: "Why Base64 and not just send the PNG file?"**
> "Sending files requires separate HTTP requests and file management on the server. Base64 embeds the image directly in the JSON response — one request, one response, no file cleanup needed. It's ~33% larger in size, but for a few charts it's negligible."

**Q: "Why `plt.close()` after every chart?"**
> "Without `plt.close()`, matplotlib keeps figures in memory. After generating 20 charts, you'd have 20 figures consuming ~200MB of RAM. On a 512MB server, this crashes the app. Always close figures after saving."

### Step 4: Data Quality Audit
```python
for col in df.columns:
    nulls = df[col].null_count()
    if nulls > 0:
        null_pct = (nulls / total_rows) * 100
        rec = "Drop Column" if null_pct > 40 else (
            "Impute with Mode" if col in cat_cols else "Impute with Median/Mean"
        )
        audit_log.append({...})
```

**Q: "What's the logic for the recommendation?"**
> - **>40% null** → Drop the column (too much missing data to reliably impute)
> - **≤40% null + categorical** → Impute with Mode (most common value)
> - **≤40% null + numeric** → Impute with Median/Mean (statistically sound)

### Step 5: Skewness Detection
```python
skew_series = df.select(pl.col(col).drop_nulls().skew())
if skew is not None and abs(skew) > 1.5:
    audit_log.append({..., 'action': 'Log Transform/Cap'})
```

**Q: "What is skewness?"**
> "Skewness measures how lopsided a distribution is. Skew = 0 means symmetric (normal distribution). Skew > 1.5 means heavily right-tailed (like income — most people earn $50K but some earn $10M). Highly skewed data breaks many ML algorithms, so we flag it and recommend log transformation."

**Q: "Why `drop_nulls()` before `skew()`?"**
> "Null values can't be used in math. Without dropping them, Polars would return `null` for the entire skew calculation."

---

## Lines 114-181: Visualization Functions

### Lazy-Loading Single Distribution

```python
def generate_single_distribution(df: pl.DataFrame, column: str, c_type: str):
    if c_type == 'numeric':
        data = df.select(column).drop_nulls().to_pandas()[column]
        sns.histplot(data, kde=True, color='#4CAF50')
    else:
        val_counts = df.select(column).to_series().drop_nulls().value_counts()
            .sort("count", descending=True).head(10).to_pandas()
        sns.barplot(data=val_counts, y=column, x="count", palette='viridis')
```

**Q: "Why different charts for numeric vs categorical?"**
> - **Numeric** → Histogram with KDE (kernel density estimation) shows the shape of the distribution. You can see if it's normal, skewed, bimodal, etc.
> - **Categorical** → Horizontal bar chart of top 10 values. Shows which categories are most common. Limited to 10 to avoid unreadable charts with 500 unique values.

**Q: "What is KDE?"**
> "Kernel Density Estimation draws a smooth curve over the histogram. Imagine placing a tiny bell curve on each data point, then adding them all up. The result shows the probability density — where data is most concentrated. `kde=True` enables this."

### Custom Chart Builder
```python
def generate_custom_chart_base64(df, x_col, y_col, hue_col, chart_type, show_reg):
    plot_df = df.select(cols_to_select).drop_nulls()
    if plot_df.height > 10000:
        plot_df = plot_df.sample(10000)   # ← SMART: Downsample for performance
    pd_df = plot_df.to_pandas()
```

**Q: "Why limit to 10,000 points?"**
> "Scatter plots with 1M points take 30+ seconds to render and produce unreadable blobs. 10,000 points show the same patterns and render in ~1 second. Polars `.sample()` randomly selects rows, preserving the distribution."

**5 Chart Types Supported:**
| Type | Seaborn Function | Best For |
|---|---|---|
| Scatter | `sns.scatterplot()` | Relationship between two numbers |
| Line | `sns.lineplot()` | Trends over time or sequence |
| Bar | `sns.barplot()` | Category vs. average numeric value |
| Box | `sns.boxplot()` | Distribution + outliers |
| Violin | `sns.violinplot()` | Distribution shape comparison |

---

## Lines 183-227: PCA (Principal Component Analysis)

```python
scaler = StandardScaler()
X_scaled = scaler.fit_transform(pd_df[num_cols])
pca = PCA(n_components=2)
components = pca.fit_transform(X_scaled)
```

**Q: "Explain PCA like I'm 5."**
> "Imagine you have a table with 20 columns of numbers. PCA finds the 2 most important 'directions' in the data and projects everything onto those 2 directions. It's like taking a 3D object and finding the best angle to photograph it in 2D — you lose some information but capture the most important patterns."

**Q: "Why StandardScaler before PCA?"**
> "PCA is based on variance. If 'Sales' ranges 0-100,000 and 'Age' ranges 18-80, PCA thinks Sales is 1000x more important just because its numbers are bigger. StandardScaler normalizes all columns to mean=0, std=1, so they contribute equally."

**Q: "What does `explained_variance_ratio_` tell you?"**
> "It tells you how much of the original information each component captures. If PCA1 explains 45% and PCA2 explains 25%, together they capture 70% of all patterns in the data. If it's below 50%, the 2D view is a poor representation."

---

## Lines 229-310: Preprocessing & Auto-Clean

### Advanced Preprocessing (Preview)
```python
def advanced_preprocessing(df: pl.DataFrame):
    df, pii_log = scrub_pii(df)          # 1. Mask PII
    pd_df = df.head(5).to_pandas()       # 2. Take only 5 rows for preview
    
    cat_cols = df.select(pl.col(pl.String, pl.Categorical, pl.Boolean)).columns
    for col in cat_cols:
        valid_vals = df[col].drop_nulls().unique()
        if len(valid_vals) == 2:          # Binary column (Yes/No, Male/Female)
            encoding_log.append(f"Binary Encoded '{col}': '{val_0}'->0, '{val_1}'->1")
    
    pd_df = pd.get_dummies(pd_df, columns=cat_cols, drop_first=True, dtype=int)
```

**Q: "What is One-Hot Encoding?"**
> "ML models only understand numbers. One-hot encoding converts `Region: [North, South, East]` into three binary columns: `Region_North: [1,0,0]`, `Region_South: [0,1,0]`, `Region_East: [0,0,1]`. `drop_first=True` removes one column (Region_North) because it can be inferred from the others — this prevents multicollinearity."

### Auto-Clean Dataset (Full Pipeline)
```python
def auto_clean_dataset(df: pl.DataFrame):
    # 1. Impute numeric nulls with median
    exprs.append(pl.col(col).fill_null(pl.col(col).median()))
    
    # 2. Impute categorical nulls with mode
    exprs.append(pl.col(col).fill_null(pl.col(col).mode().first()))
    
    # 3. Log transform skewed numerics
    if abs(skew) > 1.5:
        skew_exprs.append(pl.col(col).map_elements(lambda x: np.log1p(x)))
    
    # 4. Binary encode (2-value categoricals)
    pd_clean[col] = pd_clean[col].map({val_0: 0, val_1: 1})
    
    # 5. One-hot encode remaining categoricals
    pd_clean = pd.get_dummies(pd_clean, columns=pd_cat, drop_first=True, dtype=int)
    
    # 6. Save as ML-ready CSV
    pd_clean.to_csv(save_path, index=False)
```

**Q: "Why median instead of mean for imputation?"**
> "Mean is sensitive to outliers. If income has values [30K, 35K, 40K, 10M], the mean is ~2.5M — ridiculous. Median is 37.5K — representative. For skewed data (which is flagged in the audit), median is always safer."

---

## Lines 312-373: Transformation Studio (13 Operations)

```python
def apply_custom_transformation(df, column, transform_type):
```

| Transform | What It Does | When To Use |
|---|---|---|
| `log` | `log1p(x)` | Right-skewed data (income, prices) |
| `sqrt` | `√x` | Moderate skew, count data |
| `square` | `x²` | Left-skewed data |
| `standard_scale` | `(x - mean) / std` | Before KNN, SVM, PCA |
| `minmax_scale` | `(x - min) / (max - min)` | Scale to [0,1] range |
| `fill_mean` | Replace nulls with mean | Normally distributed columns |
| `fill_median` | Replace nulls with median | Skewed columns |
| `fill_mode` | Replace nulls with most common value | Categorical columns |
| `abs` | `|x|` | Remove negatives |
| `reciprocal` | `1/x` | Inverse relationship |
| `cap_outliers_iqr` | Clip to Q1-1.5*IQR, Q3+1.5*IQR | Remove extreme values |
| `binning_5` | Equal-width 5 bins | Convert continuous to categories |
| `label_encode` | Ordinal mapping | Categorical → numeric |

**Q: "What is IQR outlier capping?"**
```python
q1 = df[column].quantile(0.25)    # 25th percentile
q3 = df[column].quantile(0.75)    # 75th percentile
iqr = q3 - q1                      # Interquartile range
lower = q1 - 1.5 * iqr
upper = q3 + 1.5 * iqr
df.with_columns(pl.col(column).clip(lower, upper))
```
> "IQR is the range between the 25th and 75th percentiles — it covers the middle 50% of data. Anything beyond 1.5x that range from Q1 or Q3 is an outlier. `clip()` forces outlier values to the boundary instead of removing rows."

---

## Lines 375-400: Synthetic Data Generator

```python
def create_synthetic_dataset():
    np.random.seed(42)     # Same random numbers every time (reproducible)
    n = 1000
    df = pl.DataFrame({
        'Order_ID': range(1001, 1001 + n),
        'Product_Category': np.random.choice(['Tech', 'Fashion', 'Home', 'Software'], n),
        'Sales_Amount': np.random.exponential(scale=500, size=n).round(2),
        ...
    })
    
    # INTENTIONALLY inject dirty data for demo:
    pd_df.loc[0:10, 'Sales_Amount'] = 99000.0    # Outliers!
    pd_df.loc[50:150, 'Customer_Age'] = np.nan    # Missing values!
```

**Q: "Why inject dirty data on purpose?"**
> "The whole point of the platform is to DETECT issues. If the demo data was clean, the audit table would be empty and the AI report would have nothing to say. By injecting outliers (99000) and missing values (NaN), we demonstrate every feature of the platform."

**Q: "What is `np.random.seed(42)`?"**
> "Random numbers aren't truly random — they're generated by an algorithm. The 'seed' sets the starting point. Seed 42 always produces the same sequence. This means the demo data is identical every time, making it reproducible and testable."
