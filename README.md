# 📊 Data Engineer Pro — AI-Powered EDA Platform

An enterprise-grade Automated EDA (Exploratory Data Analysis) and Data Engineering platform with AI-powered insights, interactive feature engineering, and PySpark integration.

## 🚀 Features
- **Automated Data Audit** — Instant detection of missing values, skewness, and data quality issues
- **Interactive Transformation Studio** — Apply 12+ mathematical transformations (Log, Sqrt, Scaling, Outlier Capping, Binning, Label Encoding)
- **AI Data Analyst** — Chat with your dataset using Groq's Llama 3.3 70B (FREE)
- **Auto-ML Script Generator** — Generates scikit-learn training scripts tailored to your data
- **PCA & Correlation Analysis** — Dimensionality reduction and heatmaps
- **Custom Visualizations** — Scatter, Line, Bar, Box, and Violin plots
- **PySpark Operations** — Full Spark integration with Filter, GroupBy, Window Functions, and more
- **PDF Export** — One-click executive report generation
- **Dark/Light Theme** — Persistent theme with localStorage
- **Mobile Responsive** — Works on phones and tablets
- **PII Scrubbing** — Automatic redaction of sensitive data

## 📦 Quick Start (Local)
```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/data-engineer-pro.git
cd data-engineer-pro

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt

# Set your Groq API key
export GROQ_API_KEY=gsk_your_key_here
export AI_PROVIDER=groq

# Run
uvicorn backend.main:app --host 0.0.0.0 --port 8080
```
Open `http://localhost:8080` in your browser.

## 🔑 Getting a Free Groq API Key
1. Go to [console.groq.com](https://console.groq.com)
2. Sign up (free)
3. Go to API Keys → Create Key
4. Copy the key and set it as `GROQ_API_KEY`

## 🐳 Docker Deployment
```bash
docker build -t data-engineer-pro .
docker run -e GROQ_API_KEY=gsk_your_key -e AI_PROVIDER=groq -p 8080:8080 data-engineer-pro
```

## ☁️ Deploy to Render (Free)
1. Push this repo to GitHub
2. Go to [render.com](https://render.com) → New Web Service
3. Connect your GitHub repo
4. Set:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
5. Add Environment Variables:
   - `GROQ_API_KEY` = your key
   - `AI_PROVIDER` = groq
6. Deploy!

## 🛠️ Tech Stack
| Layer | Technology |
|-------|-----------|
| Backend | FastAPI + Uvicorn |
| Data Processing | Polars (Rust-based) |
| Big Data | PySpark (optional) |
| AI | Groq (Llama 3.3 70B) |
| Frontend | Vanilla HTML/CSS/JS |
| Visualizations | Matplotlib + Seaborn |

## 📱 Mobile Support
The app is fully responsive. On phones, the dashboard stacks vertically with scrollable tabs.

## 📄 License
MIT
