import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
import io
import base64
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

def perform_analysis(df: pd.DataFrame):
    """Generates statistics and missing value audits."""
    stats = df.describe(include='all').transpose()
    stats = stats.fillna('')
    
    num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    cat_cols = df.select_dtypes(exclude=[np.number]).columns.tolist()
    
    # Generate correlation heatmap image
    corr_html_str = ""
    if len(num_cols) > 1:
        corr = df[num_cols].corr(numeric_only=True)
        plt.figure(figsize=(8, 6))
        sns.heatmap(corr, annot=True, cmap='coolwarm', center=0)
        buf = io.BytesIO()
        plt.tight_layout()
        plt.savefig(buf, format='png')
        plt.close()
        corr_html_str = base64.b64encode(buf.getvalue()).decode("utf-8")
        
    audit_log = []
    total_rows = len(df)
    
    for col in df.columns:
        nulls = df[col].isnull().sum()
        if nulls > 0:
            null_pct = (nulls / total_rows) * 100
            rec = "Drop Column" if null_pct > 40 else ("Impute with Mode" if col in cat_cols else "Impute with Median/Mean")
            audit_log.append({'feature': col, 'issue': 'Missing Values', 'severity': f"{null_pct:.1f}% Null", 'action': rec})
            
    for col in num_cols:
        skew = df[col].skew()
        if pd.notna(skew) and abs(skew) > 1.5:
            audit_log.append({'feature': col, 'issue': 'High Skew', 'severity': f"Skewness: {skew:.2f}", 'action': 'Log Transform/Cap'})
            
    if not audit_log:
        audit_log.append({'feature': 'All', 'issue': 'None', 'severity': 'Clean', 'action': 'Ready'})
        
    return {
        "stats": stats.reset_index().rename(columns={"index": "feature"}).to_dict(orient="records"),
        "audit": audit_log,
        "num_cols": num_cols,
        "cat_cols": cat_cols,
        "correlation": corr_html_str,
        "shape": list(df.shape)
    }

def generate_plot_base64(df: pd.DataFrame, column: str, c_type: str):
    plt.figure(figsize=(6, 4))
    sns.set_style("whitegrid")
    try:
        if c_type == 'numeric':
            sns.histplot(df[column].dropna(), kde=True, color='#4CAF50')
        else:
            order = df[column].value_counts().index[:10]
            sns.countplot(data=df, y=column, order=order, palette='viridis')
        plt.title(f"Distribution of {column}")
        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        plt.close()
        return base64.b64encode(buf.getvalue()).decode('utf-8')
    except:
        plt.close()
        return None

def generate_visualizations(df: pd.DataFrame, num_cols: list, cat_cols: list):
    visuals = []
    # Generate for ALL columns to provide complete distributions
    for col in num_cols:
        img = generate_plot_base64(df, col, 'numeric')
        if img: visuals.append({"column": col, "type": "numeric", "image": img})
    for col in cat_cols:
        img = generate_plot_base64(df, col, 'categorical')
        if img: visuals.append({"column": col, "type": "categorical", "image": img})
    return visuals

def advanced_preprocessing(df: pd.DataFrame):
    df_encoded = df.copy()
    encoding_log = []
    
    for col in df_encoded.select_dtypes(include=['object', 'category', 'bool']).columns:
        valid_vals = df_encoded[col].dropna().unique()
        if len(valid_vals) == 2:
            val_0, val_1 = valid_vals[0], valid_vals[1]
            df_encoded[col] = df_encoded[col].map({val_0: 0, val_1: 1})
            encoding_log.append(f"Binary Encoded '{col}': '{val_0}'->0, '{val_1}'->1")
            
    cat_cols = df_encoded.select_dtypes(include=['object', 'category']).columns.tolist()
    if cat_cols:
        df_encoded = pd.get_dummies(df_encoded, columns=cat_cols, drop_first=True, dtype=int)
        encoding_log.append(f"One-Hot Encoded: {', '.join(cat_cols)}")
        
    if not encoding_log:
        encoding_log.append("No categorical columns required encoding.")
        
    # Return head of dataframe for UI preview
    preview = df_encoded.head(5).fillna('').to_dict(orient='records')
    return preview, encoding_log

def generate_custom_chart_base64(df: pd.DataFrame, x_col: str, y_col: str, hue_col: str = None, chart_type: str = "scatter", show_reg: bool = False):
    plt.figure(figsize=(10, 6))
    sns.set_style("whitegrid")
    try:
        hue_val = None if not hue_col or hue_col == "" else hue_col
        
        if chart_type == "scatter":
            if show_reg and not hue_val:
                sns.regplot(data=df, x=x_col, y=y_col, scatter_kws={'alpha':0.5}, line_kws={'color':'red'})
            else:
                sns.scatterplot(data=df, x=x_col, y=y_col, hue=hue_val, palette='viridis', alpha=0.7)
        elif chart_type == "line":
            sns.lineplot(data=df, x=x_col, y=y_col, hue=hue_val, palette='viridis')
        elif chart_type == "bar":
            sns.barplot(data=df, x=x_col, y=y_col, hue=hue_val, palette='viridis', errorbar=None)
        elif chart_type == "box":
            sns.boxplot(data=df, x=x_col, y=y_col, hue=hue_val, palette='viridis')
        elif chart_type == "violin":
            sns.violinplot(data=df, x=x_col, y=y_col, hue=hue_val, palette='viridis', split=(len(df[hue_val].dropna().unique())==2 if hue_val else False))
            
        plt.title(f"{chart_type.capitalize()} Plot: {x_col} vs {y_col}")
        plt.xticks(rotation=45)
        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        plt.close()
        return base64.b64encode(buf.getvalue()).decode('utf-8')
    except Exception as e:
        plt.close()
        return None

def generate_pca_base64(df: pd.DataFrame, num_cols: list, hue_col: str = None):
    if len(num_cols) < 2: 
        return None, "Need at least 2 numerical columns for PCA."
    
    df_clean = df.dropna(subset=num_cols).copy()
    hue_val = None if not hue_col or hue_col == "" else hue_col
    if hue_val: 
        df_clean = df_clean.dropna(subset=[hue_val])
        
    if len(df_clean) == 0: 
        return None, "Not enough clean data."

    try:
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(df_clean[num_cols])
        pca = PCA(n_components=2)
        components = pca.fit_transform(X_scaled)
        
        df_clean['PCA1'] = components[:, 0]
        df_clean['PCA2'] = components[:, 1]
        var_ratio = pca.explained_variance_ratio_
        
        plt.figure(figsize=(10, 6))
        sns.scatterplot(data=df_clean, x='PCA1', y='PCA2', hue=hue_val, palette='magma', alpha=0.8)
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

def create_synthetic_dataset():
    np.random.seed(42)
    n = 1000
    df = pd.DataFrame({
        'Order_ID': range(1001, 1001 + n),
        'Product_Category': np.random.choice(['Tech', 'Fashion', 'Home', 'Software'], n),
        'Sales_Amount': np.random.exponential(scale=500, size=n).round(2), 
        'Customer_Age': np.random.randint(18, 80, n),
        'Marketing_Spend': np.random.normal(100, 30, n).round(2),
        'Smoker': np.random.choice(['Yes', 'No'], n), 
        'Region': np.random.choice(['North America', 'EMEA', 'APAC', 'LATAM'], n),
        'Satisfaction_Score': np.random.randint(1, 6, n),
    })
    df['Sales_Amount'] += df['Marketing_Spend'] * 2.5
    df.loc[0:10, 'Sales_Amount'] = 99000.0  
    df.loc[50:150, 'Customer_Age'] = np.nan 
    
    save_path = "uploads/tcs_demo_data.csv"
    df.to_csv(save_path, index=False)
    return save_path

import uuid

def auto_clean_dataset(df: pd.DataFrame):
    """
    Automated data cleaning pipeline for Machine Learning:
    1. Imputes missing numericals (Median)
    2. Imputes missing categoricals (Mode)
    3. Log-transforms skewed numericals
    4. One-Hot Encodes categorical data
    Returns the file path to the cleaned CSV.
    """
    clean_df = df.copy()
    
    num_cols = clean_df.select_dtypes(include=[np.number]).columns.tolist()
    cat_cols = clean_df.select_dtypes(exclude=[np.number]).columns.tolist()
    
    # 1 & 2. Imputation
    for col in num_cols:
        if clean_df[col].isnull().sum() > 0:
            clean_df[col] = clean_df[col].fillna(clean_df[col].median())
            
    for col in cat_cols:
        if clean_df[col].isnull().sum() > 0:
            clean_df[col] = clean_df[col].fillna(clean_df[col].mode()[0])
            
    # 3. Log Transform High Skew
    for col in num_cols:
        skew = clean_df[col].skew()
        if pd.notna(skew) and abs(skew) > 1.5:
            # Shift to positive if there are <= 0 values
            min_val = clean_df[col].min()
            if min_val <= 0:
                clean_df[col] = np.log1p(clean_df[col] - min_val + 1)
            else:
                clean_df[col] = np.log1p(clean_df[col])
                
    # 4. Binary & One-Hot Encoding
    for col in cat_cols:
        valid_vals = clean_df[col].unique()
        if len(valid_vals) == 2:
            val_0, val_1 = valid_vals[0], valid_vals[1]
            clean_df[col] = clean_df[col].map({val_0: 0, val_1: 1})
            
    # Update categorical columns after binary encoding
    cat_cols = clean_df.select_dtypes(include=['object', 'category']).columns.tolist()
    if cat_cols:
        clean_df = pd.get_dummies(clean_df, columns=cat_cols, drop_first=True, dtype=int)
        
    # Save to file
    file_id = str(uuid.uuid4())
    save_path = f"uploads/cleaned_{file_id}.csv"
    clean_df.to_csv(save_path, index=False)
    
    return save_path

from sklearn.preprocessing import MinMaxScaler

def apply_custom_transformation(df: pd.DataFrame, column: str, transform_type: str):
    """
    Applies a specific mathematical transformation or imputation to a column.
    Returns the modified dataframe.
    """
    df_trans = df.copy()
    
    if transform_type == "log":
        min_val = df_trans[column].min()
        if min_val <= 0:
            df_trans[column] = np.log1p(df_trans[column] - min_val + 1)
        else:
            df_trans[column] = np.log1p(df_trans[column])
    elif transform_type == "sqrt":
        df_trans[column] = np.sqrt(df_trans[column].clip(lower=0))
    elif transform_type == "square":
        df_trans[column] = np.square(df_trans[column])
    elif transform_type == "standard_scale":
        scaler = StandardScaler()
        df_trans[column] = scaler.fit_transform(df_trans[[column]])
    elif transform_type == "minmax_scale":
        scaler = MinMaxScaler()
        df_trans[column] = scaler.fit_transform(df_trans[[column]])
    elif transform_type == "fill_mean":
        df_trans[column] = df_trans[column].fillna(df_trans[column].mean())
    elif transform_type == "fill_median":
        df_trans[column] = df_trans[column].fillna(df_trans[column].median())
    elif transform_type == "fill_mode":
        df_trans[column] = df_trans[column].fillna(df_trans[column].mode()[0])
        
    return df_trans
