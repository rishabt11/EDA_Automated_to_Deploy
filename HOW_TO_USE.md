# How to Use: Data Engineer Pro

## Getting Started
1. Start the backend server by activating the virtual environment and running Uvicorn:
   ```bash
   source venv/bin/activate
   uvicorn backend.main:app --host 0.0.0.0 --port 8080
   ```
2. Make sure your local LM Studio server is running on `http://127.0.0.1:1234` with an active model loaded.
3. Open your browser and navigate to `http://localhost:8080`.

## 1. Uploading Data
- Click **Upload New Dataset**.
- Select a `.csv` or `.xlsx` file.
- **Provide Business Context:** This is crucial. Tell the AI what the data is about and what your goal is (e.g., "Predicting customer churn").
- Click **🚀 Analyze & Audit Data**.
- *Note: If the system detects emails, IPs, or SSNs, it will automatically redact them for security.*

## 2. Navigating the Dashboard
The dashboard has 5 main tabs:

### 🚨 Audit & Preprocessing
- **Scorecard:** Shows total rows, missing values, and skewed columns.
- **Audit Table:** Highlights data quality issues (Nulls, Skewness, Constants) and suggests actions.
- **Interactive Transformation Studio:**
  - Select a column and a mathematical operation.
  - Options include Imputation, Scaling, and Advanced operations (Outlier Capping, Equal-Width Binning, Label Encoding).
  - Click **Apply to Data**. The backend instantly processes it via Polars and updates the dashboard.

### 📊 Distributions
- Scroll down to view dynamic distribution charts for every column.
- Charts are lazy-loaded. They only generate when they enter your screen.

### 🔍 Deep Insights (Scatter Plots)
- Select an X-axis, Y-axis, and an optional Hue (Color by category).
- Toggle **Add Regression Trend Line** if desired.
- Click **Generate Chart** for a custom, high-resolution correlation plot.

### 🎯 PCA & Correlation
- **PCA Analysis:** Select a categorical column to color the clusters by, and click **Run PCA Analysis**. The backend will apply Standard Scaling and run Principal Component Analysis (2D) to find natural clusters in your dataset.
- **Correlation Heatmap:** Automatically generated on load to show numerical relationships.

### 🧠 Auto-ML Generator
- Select the **Target Column** you want to predict.
- Select the **Model Type** (Classification or Regression).
- Click **⚙️ Generate Script**.
- A custom Python script (`train_model.py`) will download to your machine. You can run this script locally to train a baseline scikit-learn model on your cleaned data.

## 3. Interacting with the AI
- The right panel houses the AI Data Analyst.
- It will automatically generate an initial EDA Strategy Report based on the data audit.
- You can type follow-up questions in the input box.
- Click **🛑 Stop** to instantly halt the AI's response if needed.

## 4. Exporting Your Work
- **Export PDF:** Click the `📄 Export Report` button in the top navigation bar to generate a clean, white-background PDF of your entire dashboard to share with management.
- **Download Cleaned Data:** Click the `📥 Download ML-Ready CSV` button to download the finalized dataset after all your transformations.
