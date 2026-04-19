import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg') # CRITICAL: Prevents Gradio UI from freezing
import matplotlib.pyplot as plt
import seaborn as sns
import gradio as gr
import io
import base64
import traceback
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

# --- API INTEGRATION IMPORTS ---
import requests
import os
import json
import urllib3
from dotenv import load_dotenv

# Suppress InsecureRequestWarning if verify=False is used
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==========================================
# 🔑 ENVIRONMENT SETUP
# ==========================================
load_dotenv()
API_KEY = os.getenv("OPENAI_API_KEY")
BASE_URL = "https://genailab.tcs.in/v1/chat/completions"

# ==========================================
# HELPER: SAFE FILE PATH EXTRACTOR
# ==========================================
def get_filepath(file_obj):
    if file_obj is None: return None
    if isinstance(file_obj, str): return file_obj
    elif hasattr(file_obj, 'name'): return file_obj.name
    elif hasattr(file_obj, 'orig_name'): return file_obj.orig_name
    return str(file_obj)

# ==========================================
# HELPER: TCS API STREAMING ENGINE
# ==========================================
def stream_tcs_api(messages, model_name):
    """Handles the streaming connection to the TCS GenAI API."""
    if not API_KEY:
        yield "⚠️ **API Key Missing!** Please ensure you have a `.env` file in your directory containing `OPENAI_API_KEY=your_key`."
        return

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "model": model_name,
        "messages": messages,
        "temperature": 0.7,
        "stream": True 
    }

    try:
        response = requests.post(BASE_URL, headers=headers, json=data, verify=False, stream=True)

        if response.status_code != 200:
            yield f"❌ **Error {response.status_code}:** {response.text}"
            return

        for line in response.iter_lines():
            if line:
                decoded_line = line.decode('utf-8')
                if decoded_line.startswith("data: "):
                    payload = decoded_line[6:]
                    if payload == "[DONE]":
                        break
                    try:
                        chunk = json.loads(payload)
                        delta = chunk.get('choices', [{}])[0].get('delta', {})
                        content = delta.get('content', '')
                        if content:
                            yield content
                    except json.JSONDecodeError:
                        continue
    except Exception as e:
        yield f"❌ **Connection Exception:** {str(e)}"

# ==========================================
# 1. FAST DATA PROFILING ENGINE
# ==========================================
def perform_analysis(df):
    stats = df.describe(include='all').transpose()
    num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    cat_cols = df.select_dtypes(exclude=[np.number]).columns.tolist()
    correlation_matrix = df[num_cols].corr(numeric_only=True) if len(num_cols) > 1 else None
    
    audit_log = []
    total_rows = len(df)
    
    for col in df.columns:
        nulls = df[col].isnull().sum()
        if nulls > 0:
            null_pct = (nulls / total_rows) * 100
            rec = "Drop Column" if null_pct > 40 else ("Impute with Mode" if col in cat_cols else "Impute with Median/Mean")
            audit_log.append({'Feature': col, 'Issue': 'Missing Values', 'Severity': f"{null_pct:.1f}% Null", 'Recommended Action': rec})
            
    for col in num_cols:
        skew = df[col].skew()
        if abs(skew) > 1.5:
            audit_log.append({'Feature': col, 'Issue': 'High Skew / Outliers', 'Severity': f"Skewness: {skew:.2f}", 'Recommended Action': 'Apply Log Transformation or Cap Outliers'})
            
    if not audit_log:
        audit_log.append({'Feature': 'All', 'Issue': 'None Detected', 'Severity': 'Clean', 'Recommended Action': 'Ready for Modeling'})
        
    audit_df = pd.DataFrame(audit_log)
    return stats, audit_df, num_cols, cat_cols, correlation_matrix

def advanced_preprocessing(df):
    df_encoded = df.copy()
    encoding_log = []
    
    for col in df_encoded.select_dtypes(include=['object', 'category', 'bool']).columns:
        valid_vals = df_encoded[col].dropna().unique()
        if len(valid_vals) == 2:
            val_0, val_1 = valid_vals[0], valid_vals[1]
            df_encoded[col] = df_encoded[col].map({val_0: 0, val_1: 1})
            encoding_log.append(f"✅ **Binary Encoded '{col}':** '{val_0}' ➔ 0, '{val_1}' ➔ 1")
            
    cat_cols = df_encoded.select_dtypes(include=['object', 'category']).columns.tolist()
    if cat_cols:
        df_encoded = pd.get_dummies(df_encoded, columns=cat_cols, drop_first=True, dtype=int)
        encoding_log.append(f"✅ **One-Hot Encoded (Safe/No-Leak):** {', '.join(cat_cols)}")
        
    if not encoding_log:
        encoding_log.append("No categorical columns required encoding.")
        
    return df_encoded, "\n\n".join(encoding_log)

def generate_plot_base64(df, column, c_type):
    plt.figure(figsize=(6, 4))
    sns.set_style("whitegrid")
    if c_type == 'numeric':
        sns.histplot(df[column].dropna(), kde=True, color='#2E7D32')
    else:
        order = df[column].value_counts().index[:10]
        sns.countplot(data=df, y=column, order=order, palette='viridis')
    buf = io.BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format='png')
    plt.close()
    return base64.b64encode(buf.getvalue()).decode('utf-8')

def generate_all_univariate_html(df, num_cols, cat_cols):
    html_content = "<div style='display: flex; flex-wrap: wrap; gap: 15px; justify-content: center;'>"
    for col in num_cols:
        img = generate_plot_base64(df, col, 'numeric')
        html_content += f"<div style='border: 1px solid #e5e7eb; padding: 10px; border-radius: 8px; background: white;'><h4>Numerical: {col}</h4><img src='data:image/png;base64,{img}' width='350px'></div>"
    for col in cat_cols:
        img = generate_plot_base64(df, col, 'categorical')
        html_content += f"<div style='border: 1px solid #e5e7eb; padding: 10px; border-radius: 8px; background: white;'><h4>Categorical: {col}</h4><img src='data:image/png;base64,{img}' width='350px'></div>"
    html_content += "</div>"
    return html_content

def generate_scatter_base64(df, x_col, y_col, hue_col=None, show_reg=False):
    plt.figure(figsize=(10, 6))
    sns.set_style("whitegrid")
    if show_reg:
        sns.regplot(data=df, x=x_col, y=y_col, scatter_kws={'alpha':0.5}, line_kws={'color':'red'})
    else:
        sns.scatterplot(data=df, x=x_col, y=y_col, hue=hue_col, palette='viridis', alpha=0.7)
    plt.title(f"Bivariate Analysis: {x_col} vs {y_col}")
    buf = io.BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format='png')
    plt.close()
    return base64.b64encode(buf.getvalue()).decode('utf-8')

def generate_pca_base64(df, num_cols, hue_col=None):
    if len(num_cols) < 2: return None, "Need at least 2 numerical columns for PCA."
    df_clean = df.dropna(subset=num_cols)
    if hue_col: df_clean = df_clean.dropna(subset=[hue_col])
    if len(df_clean) == 0: return None, "Not enough clean data."

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(df_clean[num_cols])
    pca = PCA(n_components=2)
    components = pca.fit_transform(X_scaled)
    
    df_clean['PCA1'], df_clean['PCA2'] = components[:, 0], components[:, 1]
    var_ratio = pca.explained_variance_ratio_
    
    plt.figure(figsize=(10, 6))
    sns.scatterplot(data=df_clean, x='PCA1', y='PCA2', hue=hue_col, palette='magma', alpha=0.8)
    plt.title(f"PCA Cluster Map (Explains {sum(var_ratio)*100:.1f}% of Variance)")
    plt.xlabel(f"Principal Component 1 ({var_ratio[0]*100:.1f}%)")
    plt.ylabel(f"Principal Component 2 ({var_ratio[1]*100:.1f}%)")
    
    buf = io.BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format='png')
    plt.close()
    return base64.b64encode(buf.getvalue()).decode('utf-8'), "Success."

# ==========================================
# 2. UNIFIED AI CHAT & REPORT ENGINE
# ==========================================
def stream_ai_report_to_chat(model_name, file):
    """Generates the initial EDA Report directly into the Chatbot."""
    file_path = get_filepath(file)
    if not file_path:
        yield [["Generate EDA Strategy Report", "⚠️ No data available."]]
        return
        
    try:
        df = pd.read_csv(file_path) if file_path.endswith('.csv') else pd.read_excel(file_path)
        if len(df) > 5000: df = df.head(5000)
        
        stats, audit_df, _, _, _ = perform_analysis(df)
        
        prompt = f"""
        You are a Senior Data Scientist at TCS conducting an Exploratory Data Analysis (EDA).
        
        Dataset Shape: {df.shape}
        Data Quality Audit:
        {audit_df.to_markdown()}
        
        Statistical Profile:
        {stats.to_markdown()}
        
        Please provide a concise EDA Report structured exactly like this:
        ### 1. Data Quality Assessment
        (Explain the flaws found in the audit and how to fix them)
        
        ### 2. Key Business Insights
        (Highlight 2 interesting trends from the stats)
        
        ### 3. Next Steps for Machine Learning
        (What specific preprocessing or feature engineering should the user do next?)
        """
        
        messages = [{"role": "user", "content": prompt}]
        # Initialize the chatbot history with a fake "User command" and empty AI response
        history = [["Generate initial EDA Strategy Report", ""]]
        
        for chunk in stream_tcs_api(messages, model_name):
            if chunk.startswith("⚠️") or chunk.startswith("❌"):
                history[0][1] = chunk
                yield history
                break
            history[0][1] += chunk
            yield history
            
    except Exception as e:
        yield [["Generate initial EDA Strategy Report", f"## ❌ Processing Error\nError: {str(e)}"]]

def chat_with_data(user_message, history, model_name, file):
    """Streams follow-up interactive chat responses, aware of the initial report."""
    file_path = get_filepath(file)
    if not file_path:
        history.append([user_message, "⚠️ Please upload a dataset first."])
        yield history
        return
        
    try:
        df = pd.read_csv(file_path) if file_path.endswith('.csv') else pd.read_excel(file_path)
        
        data_shape = df.shape
        col_types = df.dtypes.astype(str).to_dict()
        
        system_prompt = f"""You are a Senior AI Engineer at TCS.
        The user is asking a follow-up question based on the initial EDA report you just generated.
        
        Dataset Context Snapshot:
        - Shape: {data_shape[0]} rows, {data_shape[1]} columns.
        - Columns and Types: {col_types}
        
        Provide helpful, concise, technical Python/Pandas answers based on this context and the chat history. 
        """
        
        messages = [{"role": "system", "content": system_prompt}]
        
        # Pass the entire conversation history (including the massive initial report) back to the AI
        for human_msg, ai_msg in history:
            messages.append({"role": "user", "content": human_msg})
            messages.append({"role": "assistant", "content": ai_msg})
            
        messages.append({"role": "user", "content": user_message})
        
        # Prepare the UI block for the new streaming answer
        history.append([user_message, ""])
        
        for chunk in stream_tcs_api(messages, model_name):
            if chunk.startswith("⚠️") or chunk.startswith("❌"):
                history[-1][1] = chunk
                yield history
                break
            history[-1][1] += chunk
            yield history
                
    except Exception as e:
        history[-1][1] = f"❌ Error processing dataset: {str(e)}"
        yield history

# ==========================================
# 3. SYNTHETIC DATA COMPONENT
# ==========================================
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
    
    save_path = "tcs_demo_data.csv"
    df.to_csv(save_path, index=False)
    return save_path

# ==========================================
# 4. UI CONSTRUCTION
# ==========================================
model_list = [
    "genailab-maas-gpt-4o", 
    "genailab-maas-gpt-3.5-turbo", 
    "genailab-maas-llama-3"
]

with gr.Blocks(theme=gr.themes.Soft(primary_hue="emerald"), title="TCS AI Data Agent") as demo:
    gr.Markdown("# 🚀 TCS Automated AI Data Agent")
    
    with gr.Row():
        with gr.Column(scale=2):
            input_file = gr.File(label="Target Dataset (CSV/XLSX)", file_types=[".csv", ".xlsx"])
            selected_model = gr.Dropdown(choices=model_list, value=model_list[0] if model_list else None, label="Select AI Model")
        
        with gr.Column(scale=1):
            analyze_btn = gr.Button("🚀 Run Analysis", variant="primary", size="lg")
            synth_btn = gr.Button("🎁 Generate Demo Data", variant="secondary")
            clear_btn = gr.Button("🧹 Clear Dashboard", variant="stop")

    error_box = gr.Markdown(visible=False)

    with gr.Column(visible=False) as dashboard_container:
        with gr.Tabs():
            # Tab 1: MERGED AI Chat & Audit Report
            with gr.Tab("🤖 EDA Report & Chat"):
                with gr.Row():
                    with gr.Column(scale=1):
                        gr.Markdown("### 🚨 Data Quality Audit")
                        gr.Markdown("*Automated scan for nulls, extreme outliers, and required cleaning steps.*")
                        audit_df_preview = gr.Dataframe(interactive=False)
                    with gr.Column(scale=2):
                        gr.Markdown("### 🧠 AI Strategy Report & Chat")
                        chatbot = gr.Chatbot(height=550, avatar_images=(None, "🤖"), show_label=False)
                        with gr.Row():
                            chat_input = gr.Textbox(scale=4, show_label=False, placeholder="Ask follow-up questions about this report or the dataset...")
                            send_btn = gr.Button("Send", scale=1, variant="primary")

            # Tab 2: Univariate
            with gr.Tab("📊 Feature Distributions"):
                univariate_gallery = gr.HTML()

            # Tab 3: Preprocessing
            with gr.Tab("⚙️ ML Preprocessing (Encoded)"):
                ml_report_md = gr.Markdown()
                ml_df_preview = gr.Dataframe(interactive=False)

            # Tab 4: Custom Scatter 
            with gr.Tab("🔍 Deep Insights (Custom Scatter)"):
                gr.Markdown("Select variables below to generate custom bivariate analyses.")
                with gr.Row():
                    x_var = gr.Dropdown(label="X-Axis (Numeric)")
                    y_var = gr.Dropdown(label="Y-Axis (Numeric)")
                    hue_var = gr.Dropdown(label="Color By (Categorical)")
                reg_toggle = gr.Checkbox(label="Add Regression Trend Line", value=False)
                plot_btn = gr.Button("Generate Scatter Plot", variant="primary")
                scatter_output = gr.HTML()

            # Tab 5: PCA
            with gr.Tab("🎯 Dimensionality Reduction (PCA)"):
                with gr.Row():
                    pca_hue = gr.Dropdown(label="Color Clusters By")
                    pca_btn = gr.Button("Run PCA Analysis", variant="primary")
                pca_output = gr.HTML()
                pca_msg = gr.Markdown()

            # Tab 6: Correlation
            with gr.Tab("🔗 Correlation Map"):
                corr_output = gr.HTML()

    # --- EVENT HANDLERS ---
    def fast_ui_processing(file):
        try:
            file_path = get_filepath(file)
            if not file_path:
                return [gr.update(visible=True, value="### ❌ Error: Please upload a file first."), gr.update(visible=False)] + [None]*10
            
            gr.Info("📊 Generating Visualizations...")
            df = pd.read_csv(file_path) if file_path.endswith('.csv') else pd.read_excel(file_path)
            
            if len(df) > 10000: df = df.head(10000)

            stats, audit_df, num_cols, cat_cols, corr = perform_analysis(df)
            encoded_df, encoding_log = advanced_preprocessing(df)
            
            html_gallery = generate_all_univariate_html(df, num_cols[:25], cat_cols[:25])
            
            corr_html_str = ""
            if corr is not None:
                plt.figure(figsize=(8, 6))
                sns.heatmap(corr, annot=True, cmap='coolwarm', center=0)
                buf = io.BytesIO()
                plt.savefig(buf, format='png')
                plt.close()
                corr_html_str = f'<div align="center"><img src="data:image/png;base64,{base64.b64encode(buf.getvalue()).decode("utf-8")}" width="60%"></div>'
            
            # Note: The chatbot gets initialized with a "Please wait" message here before the stream starts
            return [
                gr.update(visible=False), # error_box
                gr.update(visible=True),  # dashboard_container
                audit_df,                 # audit_df_preview
                html_gallery,             # univariate_gallery
                encoding_log,             # ml_report_md
                encoded_df.head(100),     # ml_df_preview
                gr.update(choices=num_cols, value=num_cols[0] if num_cols else None),       # x_var
                gr.update(choices=num_cols, value=num_cols[1] if len(num_cols)>1 else None),# y_var
                gr.update(choices=cat_cols + [None], value=None),                           # hue_var
                gr.update(choices=cat_cols + [None], value=None),                           # pca_hue
                corr_html_str,            # corr_output
                [["System", "⏳ **AI is compiling the EDA Strategy Report... Please wait.**"]] # chatbot initial state
            ]
        except Exception as e:
            error_trace = traceback.format_exc()
            error_msg = f"### ❌ Python Crashed!\n**Error:** {str(e)}\n\n```python\n{error_trace}\n```"
            return [gr.update(visible=True, value=error_msg), gr.update(visible=False)] + [None]*10

    # 1. Math/Visual Processing first -> 2. AI streams the report into the Chatbot
    analyze_btn.click(
        fn=fast_ui_processing, 
        inputs=[input_file], 
        outputs=[
            error_box, dashboard_container, audit_df_preview, univariate_gallery, ml_report_md, 
            ml_df_preview, x_var, y_var, hue_var, pca_hue, corr_output, chatbot
        ]
    ).then(
        fn=stream_ai_report_to_chat,
        inputs=[selected_model, input_file], 
        outputs=[chatbot]
    )

    # Chatbot Interactive Handlers
    chat_input.submit(
        fn=chat_with_data, 
        inputs=[chat_input, chatbot, selected_model, input_file], 
        outputs=[chatbot]
    ).then(lambda: "", None, [chat_input]) 
    
    send_btn.click(
        fn=chat_with_data, 
        inputs=[chat_input, chatbot, selected_model, input_file], 
        outputs=[chatbot]
    ).then(lambda: "", None, [chat_input])
    
    # Utility Buttons
    def update_scatter(file, x, y, h, r):
        file_path = get_filepath(file)
        if not file_path: return "Error: No file."
        df = pd.read_csv(file_path) if file_path.endswith('.csv') else pd.read_excel(file_path)
        img_str = generate_scatter_base64(df, x, y, h, r)
        return f'<div align="center"><img src="data:image/png;base64,{img_str}" width="75%"></div>'

    plot_btn.click(fn=update_scatter, inputs=[input_file, x_var, y_var, hue_var, reg_toggle], outputs=scatter_output)

    def run_pca(file, hue):
        file_path = get_filepath(file)
        if not file_path: return "", "Error: No file."
        df = pd.read_csv(file_path) if file_path.endswith('.csv') else pd.read_excel(file_path)
        num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        img_str, msg = generate_pca_base64(df, num_cols, hue)
        if img_str: return f'<div align="center"><img src="data:image/png;base64,{img_str}" width="80%"></div>', msg
        return "", msg

    pca_btn.click(fn=run_pca, inputs=[input_file, pca_hue], outputs=[pca_output, pca_msg])
    
    synth_btn.click(fn=create_synthetic_dataset, outputs=input_file)
    clear_btn.click(fn=lambda: (None, gr.update(visible=False)), outputs=[input_file, dashboard_container])

if __name__ == "__main__":
    demo.launch(share=False)