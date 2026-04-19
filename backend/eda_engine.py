import polars as pl
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
import io
import base64
import uuid
import os

# --- PII SCRUBBING ---
def scrub_pii(df: pl.DataFrame):
    """Detects and masks PII in string columns."""
    str_cols = df.select(pl.col(pl.String)).columns
    if not str_cols:
        return df, []
        
    log = []
    # Basic Regex for Email and Phone numbers (simplified)
    email_regex = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    
    exprs = []
    for col in str_cols:
        # Check if column name suggests PII
        c_lower = col.lower()
        if any(kw in c_lower for kw in ['email', 'phone', 'ssn', 'credit', 'card', 'name', 'ip_address']):
            exprs.append(pl.lit("[REDACTED]").alias(col))
            log.append(f"Masked entire column '{col}' due to PII keyword match.")
            continue
            
        # Or check if data contains @ symbols frequently (basic email check without heavy regex map)
        # Using string contains on polars is fast
        email_count = df.select(pl.col(col).str.contains("@")).sum()[0, 0]
        if email_count and email_count > (df.height * 0.1): # 10% of rows have @
            exprs.append(pl.lit("[REDACTED_EMAIL]").alias(col))
            log.append(f"Masked column '{col}' due to high email density.")
            
    if exprs:
        df = df.with_columns(exprs)
        
    return df, log

# --- CORE EDA ---
def perform_analysis(df: pl.DataFrame):
    """Generates statistics and missing value audits using Polars."""
    
    # 1. Basic Stats
    # Polars describe returns a DataFrame. We transpose it to match Pandas style.
    stats_df = df.describe()
    
    # We need to reshape polars describe: columns are 'statistic', then each column in df.
    # We want rows to be features.
    cols = [col for col in stats_df.columns if col != 'statistic']
    
    stats_list = []
    for col in cols:
        col_stats = {"feature": col}
        for i, row in enumerate(stats_df.iter_rows(named=True)):
            stat_name = row['statistic']
            col_stats[stat_name] = row[col]
        stats_list.append(col_stats)
        
    num_cols = df.select(pl.col(pl.NUMERIC_DTYPES)).columns
    cat_cols = [col for col in df.columns if col not in num_cols]
    
    # Generate correlation heatmap image
    corr_html_str = ""
    if len(num_cols) > 1:
        # Calculate correlation matrix using polars
        # Polars native corr doesn't return a full matrix dataframe easily for plotting, 
        # so we convert just the numeric subset to pandas for the heatmap calculation
        pd_num = df.select(num_cols).to_pandas()
        corr = pd_num.corr()
        plt.figure(figsize=(8, 6))
        sns.heatmap(corr, annot=True, cmap='coolwarm', center=0)
        buf = io.BytesIO()
        plt.tight_layout()
        plt.savefig(buf, format='png')
        plt.close()
        corr_html_str = base64.b64encode(buf.getvalue()).decode("utf-8")
        
    audit_log = []
    total_rows = df.height
    
    for col in df.columns:
        nulls = df[col].null_count()
        if nulls > 0:
            null_pct = (nulls / total_rows) * 100
            rec = "Drop Column" if null_pct > 40 else ("Impute with Mode" if col in cat_cols else "Impute with Median/Mean")
            audit_log.append({'feature': col, 'issue': 'Missing Values', 'severity': f"{null_pct:.1f}% Null", 'action': rec})
            
    for col in num_cols:
        # Polars skew requires drop_nulls
        skew_series = df.select(pl.col(col).drop_nulls().skew())
        if skew_series.height > 0:
            skew = skew_series[0, 0]
            if skew is not None and abs(skew) > 1.5:
                audit_log.append({'feature': col, 'issue': 'High Skew', 'severity': f"Skewness: {skew:.2f}", 'action': 'Log Transform/Cap'})
            
    if not audit_log:
        audit_log.append({'feature': 'All', 'issue': 'None', 'severity': 'Clean', 'action': 'Ready'})
        
    return {
        "stats": stats_list,
        "audit": audit_log,
        "num_cols": num_cols,
        "cat_cols": cat_cols,
        "correlation": corr_html_str,
        "shape": [df.height, df.width]
    }

# --- VISUALIZATIONS (LAZY LOADING READY) ---
def generate_single_distribution(df: pl.DataFrame, column: str, c_type: str):
    """Generates a single base64 plot. We convert just 1 column to pandas."""
    plt.figure(figsize=(6, 4))
    sns.set_style("whitegrid")
    try:
        if c_type == 'numeric':
            data = df.select(column).drop_nulls().to_pandas()[column]
            sns.histplot(data, kde=True, color='#4CAF50')
        else:
            # Get top 10 value counts
            val_counts = df.select(column).to_series().drop_nulls().value_counts().sort("count", descending=True).head(10).to_pandas()
            sns.barplot(data=val_counts, y=column, x="count", palette='viridis')
            
        plt.title(f"Distribution of {column}")
        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        plt.close()
        return base64.b64encode(buf.getvalue()).decode('utf-8')
    except Exception as e:
        print(f"Error plotting {column}: {str(e)}")
        plt.close()
        return None

def generate_custom_chart_base64(df: pl.DataFrame, x_col: str, y_col: str, hue_col: str = None, chart_type: str = "scatter", show_reg: bool = False):
    plt.figure(figsize=(10, 6))
    sns.set_style("whitegrid")
    try:
        hue_val = None if not hue_col or hue_col == "" else hue_col
        
        # Select only required columns and convert to Pandas for Seaborn
        cols_to_select = [x_col, y_col]
        if hue_val: cols_to_select.append(hue_val)
        
        # Sample if the dataset is still massively huge to avoid browser hang on scatter plots
        # Polars sample is very fast
        plot_df = df.select(cols_to_select).drop_nulls()
        if plot_df.height > 10000:
            plot_df = plot_df.sample(10000)
            
        pd_df = plot_df.to_pandas()
        
        if chart_type == "scatter":
            if show_reg and not hue_val:
                sns.regplot(data=pd_df, x=x_col, y=y_col, scatter_kws={'alpha':0.5}, line_kws={'color':'red'})
            else:
                sns.scatterplot(data=pd_df, x=x_col, y=y_col, hue=hue_val, palette='viridis', alpha=0.7)
        elif chart_type == "line":
            sns.lineplot(data=pd_df, x=x_col, y=y_col, hue=hue_val, palette='viridis')
        elif chart_type == "bar":
            sns.barplot(data=pd_df, x=x_col, y=y_col, hue=hue_val, palette='viridis', errorbar=None)
        elif chart_type == "box":
            sns.boxplot(data=pd_df, x=x_col, y=y_col, hue=hue_val, palette='viridis')
        elif chart_type == "violin":
            sns.violinplot(data=pd_df, x=x_col, y=y_col, hue=hue_val, palette='viridis', split=(len(pd_df[hue_val].unique())==2 if hue_val else False))
            
        plt.title(f"{chart_type.capitalize()} Plot: {x_col} vs {y_col}")
        plt.xticks(rotation=45)
        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        plt.close()
        return base64.b64encode(buf.getvalue()).decode('utf-8')
    except Exception as e:
        print(f"Chart error: {e}")
        plt.close()
        return None

from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

def generate_pca_base64(df: pl.DataFrame, num_cols: list, hue_col: str = None):
    if len(num_cols) < 2: 
        return None, "Need at least 2 numerical columns for PCA."
    
    hue_val = None if not hue_col or hue_col == "" else hue_col
    cols_to_select = num_cols.copy()
    if hue_val: cols_to_select.append(hue_val)
    
    df_clean = df.select(cols_to_select).drop_nulls()
    
    if df_clean.height == 0: 
        return None, "Not enough clean data."
        
    if df_clean.height > 10000:
        df_clean = df_clean.sample(10000)
        
    pd_df = df_clean.to_pandas()

    try:
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(pd_df[num_cols])
        pca = PCA(n_components=2)
        components = pca.fit_transform(X_scaled)
        
        pd_df['PCA1'] = components[:, 0]
        pd_df['PCA2'] = components[:, 1]
        var_ratio = pca.explained_variance_ratio_
        
        plt.figure(figsize=(10, 6))
        sns.scatterplot(data=pd_df, x='PCA1', y='PCA2', hue=hue_val, palette='magma', alpha=0.8)
        plt.title(f"PCA Cluster Map (Explains {sum(var_ratio)*100:.1f}% of Variance)")
        plt.xlabel(f"Principal Component 1 ({var_ratio[0]*100:.1f}%)")
        plt.ylabel(f"Principal Component 2 ({var_ratio[1]*100:.1f}%)")
        
        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        plt.close()
        return base64.b64encode(buf.getvalue()).decode('utf-8'), "Success."
    except Exception as e:
        plt.close()
        return None, f"PCA Failed: {str(e)}"

# --- PREPROCESSING PIPELINE ---
def advanced_preprocessing(df: pl.DataFrame):
    """
    Returns an encoding log and a UI preview.
    """
    encoding_log = []
    
    # PII Scrubbing
    df, pii_log = scrub_pii(df)
    encoding_log.extend(pii_log)
    
    pd_df = df.head(5).to_pandas()
    
    cat_cols = df.select(pl.col(pl.String, pl.Categorical, pl.Boolean)).columns
    for col in cat_cols:
        valid_vals = df[col].drop_nulls().unique()
        if len(valid_vals) == 2:
            val_0, val_1 = valid_vals[0], valid_vals[1]
            encoding_log.append(f"Binary Encoded '{col}': '{val_0}'->0, '{val_1}'->1")
            
    if cat_cols:
        encoding_log.append(f"One-Hot Encoded: {', '.join(cat_cols)}")
        pd_df = pd.get_dummies(pd_df, columns=cat_cols, drop_first=True, dtype=int)
        
    if not encoding_log:
        encoding_log.append("No categorical columns required encoding.")
        
    preview = pd_df.fillna('').to_dict(orient='records')
    return preview, encoding_log

def auto_clean_dataset(df: pl.DataFrame):
    num_cols = df.select(pl.col(pl.NUMERIC_DTYPES)).columns
    cat_cols = [c for c in df.columns if c not in num_cols]
    
    exprs = []
    
    # 1. Impute Numerics with Median
    for col in num_cols:
        if df[col].null_count() > 0:
            exprs.append(pl.col(col).fill_null(pl.col(col).median()))
            
    # 2. Impute Categoricals with Mode
    for col in cat_cols:
        if df[col].null_count() > 0:
            exprs.append(pl.col(col).fill_null(pl.col(col).mode().first()))
            
    clean_df = df.with_columns(exprs)
    
    # 3. Log Transform Skewed Numerics
    skew_exprs = []
    for col in num_cols:
        skew_series = clean_df.select(pl.col(col).drop_nulls().skew())
        if skew_series.height > 0:
            skew = skew_series[0, 0]
            if skew is not None and abs(skew) > 1.5:
                # Log1p(x - min + 1)
                min_val = clean_df[col].min()
                if min_val <= 0:
                    skew_exprs.append(pl.col(col).map_elements(lambda x: np.log1p(x - min_val + 1) if x is not None else x, return_dtype=pl.Float64))
                else:
                    skew_exprs.append(pl.col(col).map_elements(lambda x: np.log1p(x) if x is not None else x, return_dtype=pl.Float64))
                    
    if skew_exprs:
        clean_df = clean_df.with_columns(skew_exprs)
        
    # Convert to Pandas for One-Hot encoding before export
    pd_clean = clean_df.to_pandas()
    
    for col in cat_cols:
        valid_vals = pd_clean[col].unique()
        if len(valid_vals) == 2:
            val_0, val_1 = valid_vals[0], valid_vals[1]
            pd_clean[col] = pd_clean[col].map({val_0: 0, val_1: 1})
            
    pd_cat = pd_clean.select_dtypes(include=['object', 'category']).columns.tolist()
    if pd_cat:
        pd_clean = pd.get_dummies(pd_clean, columns=pd_cat, drop_first=True, dtype=int)
        
    file_id = str(uuid.uuid4())
    save_path = f"uploads/cleaned_{file_id}.csv"
    pd_clean.to_csv(save_path, index=False)
    return save_path

def apply_custom_transformation(df: pl.DataFrame, column: str, transform_type: str):
    if transform_type == "log":
        min_val = df[column].min()
        if min_val <= 0:
            return df.with_columns(pl.col(column).map_elements(lambda x: np.log1p(x - min_val + 1) if x is not None else x, return_dtype=pl.Float64))
        else:
            return df.with_columns(pl.col(column).map_elements(lambda x: np.log1p(x) if x is not None else x, return_dtype=pl.Float64))
    elif transform_type == "sqrt":
        return df.with_columns(pl.col(column).map_elements(lambda x: np.sqrt(max(0, x)) if x is not None else x, return_dtype=pl.Float64))
    elif transform_type == "square":
        return df.with_columns((pl.col(column) ** 2))
    elif transform_type == "standard_scale":
        mean = df[column].mean()
        std = df[column].std()
        return df.with_columns((pl.col(column) - mean) / std)
    elif transform_type == "minmax_scale":
        col_min = df[column].min()
        col_max = df[column].max()
        return df.with_columns((pl.col(column) - col_min) / (col_max - col_min))
    elif transform_type == "fill_mean":
        return df.with_columns(pl.col(column).fill_null(pl.col(column).mean()))
    elif transform_type == "fill_median":
        return df.with_columns(pl.col(column).fill_null(pl.col(column).median()))
    elif transform_type == "fill_mode":
        return df.with_columns(pl.col(column).fill_null(pl.col(column).mode().first()))
    elif transform_type == "abs":
        return df.with_columns(pl.col(column).abs())
    elif transform_type == "reciprocal":
        # Handle zero division safely by replacing zeros with a tiny number or null
        return df.with_columns(
            pl.when(pl.col(column) != 0).then(1.0 / pl.col(column)).otherwise(None).alias(column)
        )
    elif transform_type == "cap_outliers_iqr":
        # Calculate Q1, Q3, and IQR
        q1 = df[column].quantile(0.25)
        q3 = df[column].quantile(0.75)
        iqr = q3 - q1
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr
        return df.with_columns(
            pl.col(column).clip(lower_bound, upper_bound)
        )
    elif transform_type == "binning_5":
        # Equal-width binning using cut
        min_val = df[column].min()
        max_val = df[column].max()
        if min_val is None or max_val is None or min_val == max_val:
            return df
        step = (max_val - min_val) / 5
        breaks = [min_val + step * i for i in range(1, 5)]
        
        binned = df.select(pl.col(column)).to_series().cut(breaks, labels=["Bin 1", "Bin 2", "Bin 3", "Bin 4", "Bin 5"])
        return df.with_columns(binned.alias(column))
    elif transform_type == "label_encode":
        # Ordinal label encoding
        unique_vals = df[column].drop_nulls().unique().to_list()
        mapping = {val: i for i, val in enumerate(unique_vals)}
        return df.with_columns(
            pl.col(column).replace(mapping).cast(pl.Int64)
        )
        
    return df

def create_synthetic_dataset():
    np.random.seed(42)
    n = 1000
    df = pl.DataFrame({
        'Order_ID': range(1001, 1001 + n),
        'Product_Category': np.random.choice(['Tech', 'Fashion', 'Home', 'Software'], n),
        'Sales_Amount': np.random.exponential(scale=500, size=n).round(2), 
        'Customer_Age': np.random.randint(18, 80, n),
        'Marketing_Spend': np.random.normal(100, 30, n).round(2),
        'Smoker': np.random.choice(['Yes', 'No'], n), 
        'Region': np.random.choice(['North America', 'EMEA', 'APAC', 'LATAM'], n),
        'Satisfaction_Score': np.random.randint(1, 6, n),
    })
    
    df = df.with_columns([
        (pl.col('Sales_Amount') + pl.col('Marketing_Spend') * 2.5).alias('Sales_Amount')
    ])
    
    pd_df = df.to_pandas()
    pd_df.loc[0:10, 'Sales_Amount'] = 99000.0  
    pd_df.loc[50:150, 'Customer_Age'] = np.nan 
    
    save_path = "uploads/tcs_demo_data.csv"
    pd_df.to_csv(save_path, index=False)
    return save_path
