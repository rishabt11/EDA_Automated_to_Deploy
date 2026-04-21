from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Path, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse, HTMLResponse
from pydantic import BaseModel
import polars as pl
import io
import json
import os
import uuid
import re
import time
from pathlib import Path as FilePath

# Load .env for local development (ignored in Docker where env vars are set directly)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not required in production

from backend.eda_engine import perform_analysis, advanced_preprocessing, generate_custom_chart_base64, generate_pca_base64, create_synthetic_dataset, auto_clean_dataset, apply_custom_transformation, generate_single_distribution
from backend.ai_engine import generate_initial_report, chat_with_data

app = FastAPI(title="Automated EDA AI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create necessary directories
os.makedirs("uploads", exist_ok=True)
os.makedirs("sessions", exist_ok=True)

# Session Manager
def is_valid_uuid(val: str):
    return bool(re.match(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', str(val).lower()))

def get_session(session_id: str):
    if not is_valid_uuid(session_id):
        raise HTTPException(status_code=400, detail="Invalid session format. Possible path traversal attempt.")
        
    json_path = f"sessions/{session_id}.json"
    parquet_path = f"sessions/{session_id}.parquet"
    if not os.path.exists(json_path) or not os.path.exists(parquet_path):
        raise HTTPException(status_code=400, detail="Invalid or expired session.")
    with open(json_path, 'r') as f:
        meta = json.load(f)
    df = pl.read_parquet(parquet_path)
    return meta, df

def save_session(session_id: str, meta: dict, df: pl.DataFrame):
    json_path = f"sessions/{session_id}.json"
    parquet_path = f"sessions/{session_id}.parquet"
    with open(json_path, 'w') as f:
        json.dump(meta, f)
    df.write_parquet(parquet_path)

@app.post("/api/upload")
async def upload_file(
    file: UploadFile = File(...),
    context: str = Form("")
):
    try:
        contents = await file.read()
        
        # Read dataset using Polars
        if file.filename.endswith('.csv'):
            df = pl.read_csv(io.BytesIO(contents), ignore_errors=True)
        elif file.filename.endswith(('.xls', '.xlsx')):
            df = pl.read_excel(io.BytesIO(contents))
        else:
            raise HTTPException(status_code=400, detail="Invalid file type.")
            
        # NO 10K LIMIT - Polars handles millions of rows effortlessly.
            
        eda_results = perform_analysis(df)
        encoded_preview, encoding_log = advanced_preprocessing(df)
        
        session_id = str(uuid.uuid4())
        
        meta = {
            "context": context,
            "stats": eda_results["stats"],
            "audit": eda_results["audit"],
            "num_cols": eda_results["num_cols"],
            "cat_cols": eda_results["cat_cols"],
            "shape": eda_results["shape"]
        }
        
        save_session(session_id, meta, df)
        
        # Notice: We are NOT generating visuals here to prevent crashing the server/browser.
        return {
            "session_id": session_id,
            "audit": eda_results["audit"],
            "shape": eda_results["shape"],
            "correlation": eda_results["correlation"],
            "encoding_log": encoding_log,
            "encoded_preview": encoded_preview,
            "num_cols": eda_results["num_cols"],
            "cat_cols": eda_results["cat_cols"]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/visual/{session_id}/{column}")
async def get_visual(session_id: str, column: str):
    """Lazy loads a single distribution visualization."""
    meta, df = get_session(session_id)
    if column in meta["num_cols"]:
        c_type = "numeric"
    elif column in meta["cat_cols"]:
        c_type = "categorical"
    else:
        raise HTTPException(status_code=400, detail="Column not found.")
        
    img = generate_single_distribution(df, column, c_type)
    if not img:
        raise HTTPException(status_code=500, detail="Could not generate visual.")
    return {"image": img}

@app.get("/api/ai/report")
async def get_report(session_id: str = Header(None)):
    if not session_id: raise HTTPException(status_code=400, detail="Missing session_id")
    meta, df = get_session(session_id)
        
    # SMART AI CONTEXT CHUNKING
    # Only pass 'Warning' and 'Danger' issues to the AI, otherwise it exceeds Context Window
    critical_audit = [issue for issue in meta["audit"] if "warning" in issue['severity'].lower() or "danger" in issue['severity'].lower() or issue['feature'] == 'All']
    
    return StreamingResponse(
        generate_initial_report(
            meta["context"], 
            meta["stats"], 
            critical_audit, 
            meta["shape"]
        ),
        media_type="text/event-stream"
    )

class ChatRequest(BaseModel):
    message: str
    history: list
    session_id: str

@app.post("/api/ai/chat")
async def chat(req: ChatRequest):
    if not req.session_id: raise HTTPException(status_code=400, detail="Missing session_id")
    meta, df = get_session(req.session_id)
    return StreamingResponse(
        chat_with_data(req.message, req.history, meta["context"], df),
        media_type="text/event-stream"
    )

class ChartRequest(BaseModel):
    session_id: str
    x: str
    y: str
    hue: str = None
    chart_type: str = "scatter"
    reg: bool = False

@app.post("/api/chart")
async def get_chart(req: ChartRequest):
    if not req.session_id: raise HTTPException(status_code=400, detail="Missing session_id")
    meta, df = get_session(req.session_id)
    img = generate_custom_chart_base64(df, req.x, req.y, req.hue, req.chart_type, req.reg)
    if not img: raise HTTPException(status_code=500, detail="Could not generate plot")
    return {"image": img}

class PcaRequest(BaseModel):
    session_id: str
    hue: str = None

@app.post("/api/pca")
async def get_pca(req: PcaRequest):
    if not req.session_id: raise HTTPException(status_code=400, detail="Missing session_id")
    meta, df = get_session(req.session_id)
    img, msg = generate_pca_base64(df, meta["num_cols"], req.hue)
    if not img: raise HTTPException(status_code=400, detail=msg)
    return {"image": img, "message": msg}

@app.get("/api/synthetic")
async def get_synthetic():
    path = create_synthetic_dataset()
    return FileResponse(path, media_type='text/csv', filename="demo_data.csv")

@app.get("/api/clean")
async def clean_dataset(session_id: str = Header(None)):
    if not session_id: raise HTTPException(status_code=400, detail="Missing session_id")
    try:
        meta, df = get_session(session_id)
        path = auto_clean_dataset(df)
        return FileResponse(path, media_type='text/csv', filename="ml_ready_dataset.csv")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clean dataset: {str(e)}")

class TransformRequest(BaseModel):
    session_id: str
    column: str
    transform_type: str

@app.post("/api/transform")
async def transform_column(req: TransformRequest):
    if not req.session_id: raise HTTPException(status_code=400, detail="Missing session_id")
    
    try:
        meta, df = get_session(req.session_id)
        
        # Apply transformation in Polars
        df_trans = apply_custom_transformation(df, req.column, req.transform_type)
        
        # Re-run EDA
        eda_results = perform_analysis(df_trans)
        encoded_preview, encoding_log = advanced_preprocessing(df_trans)
        
        # Update Session
        meta["stats"] = eda_results["stats"]
        meta["audit"] = eda_results["audit"]
        meta["num_cols"] = eda_results["num_cols"]
        meta["cat_cols"] = eda_results["cat_cols"]
        meta["shape"] = eda_results["shape"]
        save_session(req.session_id, meta, df_trans)
        
        return {
            "message": f"Successfully applied '{req.transform_type}' to '{req.column}'",
            "audit": eda_results["audit"],
            "shape": eda_results["shape"],
            "correlation": eda_results["correlation"],
            "encoding_log": encoding_log,
            "encoded_preview": encoded_preview,
            "num_cols": eda_results["num_cols"],
            "cat_cols": eda_results["cat_cols"]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transformation failed: {str(e)}")

class AutomlRequest(BaseModel):
    session_id: str
    target_column: str
    model_type: str = "classification"

@app.post("/api/automl")
async def generate_automl(req: AutomlRequest):
    if not req.session_id: raise HTTPException(status_code=400, detail="Missing session_id")
    meta, df = get_session(req.session_id)
    
    if req.target_column not in df.columns:
        raise HTTPException(status_code=400, detail="Target column not found")
        
    # Generate python script
    script = f'''"""
Auto-Generated ML Baseline Script
Target: {req.target_column}
Type: {req.model_type.capitalize()}
"""
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.metrics import classification_report, mean_squared_error

# Load your cleaned dataset
df = pd.read_csv("ml_ready_dataset.csv")

# Separate Features and Target
X = df.drop(columns=["{req.target_column}"])
y = df["{req.target_column}"]

# Split data
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Train baseline model
'''
    if req.model_type == "classification":
        script += '''model = RandomForestClassifier(n_estimators=100, random_state=42)
model.fit(X_train, y_train)

# Evaluate
preds = model.predict(X_test)
print(classification_report(y_test, preds))
'''
    else:
        script += '''model = RandomForestRegressor(n_estimators=100, random_state=42)
model.fit(X_train, y_train)

# Evaluate
preds = model.predict(X_test)
print(f"MSE: {mean_squared_error(y_test, preds)}")
'''
    
    return StreamingResponse(
        io.StringIO(script), 
        media_type="text/x-python",
        headers={"Content-Disposition": f"attachment; filename=train_model.py"}
    )

# ============================================================
# PySpark Endpoints
# ============================================================

# Lazy import to avoid startup crash if PySpark is not installed
spark_available = False
try:
    from backend.spark_engine import (
        get_spark, load_csv, get_schema_info, get_preview,
        filter_rows, drop_nulls, fill_nulls, replace_values, drop_duplicates,
        select_columns, add_or_modify_column, drop_column, rename_column, 
        cast_column, conditional_column,
        group_and_aggregate, simple_count,
        sort_data, join_dataframes,
        add_row_number, add_rank, add_lag_lead, add_running_total,
        apply_udf_example,
        save_as_csv, save_as_parquet,
        describe_data, summary_data,
        spark_perform_analysis, spark_apply_transformation
    )
    spark_available = True
except ImportError:
    pass

@app.get("/api/spark/status")
async def spark_status():
    """Check if PySpark is available on this server."""
    return {"available": spark_available}

class SparkLoadRequest(BaseModel):
    session_id: str

@app.post("/api/spark/load")
async def spark_load_session(req: SparkLoadRequest):
    """Load session data into Spark and return schema + preview."""
    if not spark_available:
        raise HTTPException(status_code=501, detail="PySpark is not installed on this server.")
    if not req.session_id:
        raise HTTPException(status_code=400, detail="Missing session_id")
    
    meta, _ = get_session(req.session_id)
    parquet_path = f"sessions/{req.session_id}.parquet"
    
    sdf = load_csv(parquet_path) if not os.path.exists(parquet_path) else get_spark().read.parquet(parquet_path)
    
    schema = get_schema_info(sdf)
    preview = get_preview(sdf, 5)
    row_count = simple_count(sdf)
    
    return {
        "schema": schema,
        "preview": preview,
        "row_count": row_count,
        "col_count": len(sdf.columns)
    }

class SparkAnalyzeRequest(BaseModel):
    session_id: str

@app.post("/api/spark/analyze")
async def spark_analyze_session(req: SparkAnalyzeRequest):
    """Run full Spark EDA on a session dataset."""
    if not spark_available:
        raise HTTPException(status_code=501, detail="PySpark is not installed on this server.")
    
    meta, _ = get_session(req.session_id)
    parquet_path = f"sessions/{req.session_id}.parquet"
    sdf = get_spark().read.parquet(parquet_path)
    
    analysis = spark_perform_analysis(sdf)
    return analysis

class SparkTransformRequest(BaseModel):
    session_id: str
    column: str
    transform_type: str

@app.post("/api/spark/transform")
async def spark_transform(req: SparkTransformRequest):
    """Apply a PySpark transformation to a column."""
    if not spark_available:
        raise HTTPException(status_code=501, detail="PySpark is not installed on this server.")
    
    meta, _ = get_session(req.session_id)
    parquet_path = f"sessions/{req.session_id}.parquet"
    sdf = get_spark().read.parquet(parquet_path)
    
    try:
        sdf_transformed = spark_apply_transformation(sdf, req.column, req.transform_type)
        
        # Save back to parquet
        sdf_transformed.write.mode("overwrite").parquet(parquet_path + "_tmp")
        # Read from tmp and overwrite original
        import shutil
        if os.path.exists(parquet_path):
            os.remove(parquet_path)
        # Spark writes parquet as a directory, so we need to handle this
        # Convert back to Polars for storage compatibility
        pdf = sdf_transformed.toPandas()
        pl_df = pl.from_pandas(pdf)
        pl_df.write_parquet(parquet_path)
        
        # Clean up tmp
        tmp_path = parquet_path + "_tmp"
        if os.path.exists(tmp_path):
            shutil.rmtree(tmp_path)
        
        # Re-analyze
        sdf_new = get_spark().read.parquet(parquet_path)
        analysis = spark_perform_analysis(sdf_new)
        preview = get_preview(sdf_new, 5)
        
        return {
            "message": f"[Spark] Applied '{req.transform_type}' to '{req.column}'",
            "preview": preview,
            "analysis": analysis
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Spark transformation failed: {str(e)}")

class SparkDescribeRequest(BaseModel):
    session_id: str
    columns: list = []

@app.post("/api/spark/describe")
async def spark_describe(req: SparkDescribeRequest):
    """Run describe() or summary() on the Spark DataFrame."""
    if not spark_available:
        raise HTTPException(status_code=501, detail="PySpark is not installed on this server.")
    
    meta, _ = get_session(req.session_id)
    parquet_path = f"sessions/{req.session_id}.parquet"
    sdf = get_spark().read.parquet(parquet_path)
    
    cols = req.columns if req.columns else None
    desc = describe_data(sdf, cols)
    summ = summary_data(sdf, cols)
    
    return {"describe": desc, "summary": summ}

class SparkFilterRequest(BaseModel):
    session_id: str
    column: str
    operator: str
    value: str

@app.post("/api/spark/filter")
async def spark_filter(req: SparkFilterRequest):
    """Filter rows using PySpark."""
    if not spark_available:
        raise HTTPException(status_code=501, detail="PySpark is not installed on this server.")
    
    meta, _ = get_session(req.session_id)
    parquet_path = f"sessions/{req.session_id}.parquet"
    sdf = get_spark().read.parquet(parquet_path)
    
    # Try numeric conversion
    try:
        val = float(req.value)
    except ValueError:
        val = req.value
    
    filtered = filter_rows(sdf, req.column, req.operator, val)
    preview = get_preview(filtered, 10)
    count = simple_count(filtered)
    
    return {"preview": preview, "row_count": count, "message": f"Filtered: {req.column} {req.operator} {req.value}"}

class SparkGroupRequest(BaseModel):
    session_id: str
    group_cols: list
    agg_dict: dict

@app.post("/api/spark/groupby")
async def spark_groupby(req: SparkGroupRequest):
    """Group and aggregate using PySpark."""
    if not spark_available:
        raise HTTPException(status_code=501, detail="PySpark is not installed on this server.")
    
    meta, _ = get_session(req.session_id)
    parquet_path = f"sessions/{req.session_id}.parquet"
    sdf = get_spark().read.parquet(parquet_path)
    
    try:
        result = group_and_aggregate(sdf, req.group_cols, req.agg_dict)
        preview = get_preview(result, 20)
        return {"result": preview, "message": f"Grouped by {req.group_cols}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class SparkWindowRequest(BaseModel):
    session_id: str
    partition_col: str
    order_col: str
    func: str = "row_number"
    target_col: str = ""
    offset: int = 1

@app.post("/api/spark/window")
async def spark_window(req: SparkWindowRequest):
    """Apply Window functions using PySpark."""
    if not spark_available:
        raise HTTPException(status_code=501, detail="PySpark is not installed on this server.")
    
    meta, _ = get_session(req.session_id)
    parquet_path = f"sessions/{req.session_id}.parquet"
    sdf = get_spark().read.parquet(parquet_path)
    
    try:
        if req.func == "row_number":
            result = add_row_number(sdf, req.partition_col, req.order_col)
        elif req.func in ("rank", "dense_rank"):
            result = add_rank(sdf, req.partition_col, req.order_col, req.func)
        elif req.func in ("lag", "lead"):
            result = add_lag_lead(sdf, req.partition_col, req.order_col, req.target_col, req.offset, req.func)
        elif req.func == "cumsum":
            result = add_running_total(sdf, req.partition_col, req.order_col, req.target_col)
        else:
            raise HTTPException(status_code=400, detail=f"Unknown window function: {req.func}")
        
        preview = get_preview(result, 15)
        return {"result": preview, "message": f"Applied {req.func} partitioned by {req.partition_col}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class SparkSortRequest(BaseModel):
    session_id: str
    column: str
    ascending: bool = True

@app.post("/api/spark/sort")
async def spark_sort(req: SparkSortRequest):
    """Sort data using PySpark."""
    if not spark_available:
        raise HTTPException(status_code=501, detail="PySpark is not installed on this server.")
    
    meta, _ = get_session(req.session_id)
    parquet_path = f"sessions/{req.session_id}.parquet"
    sdf = get_spark().read.parquet(parquet_path)
    
    sorted_sdf = sort_data(sdf, req.column, req.ascending)
    preview = get_preview(sorted_sdf, 15)
    return {"result": preview, "message": f"Sorted by {req.column} ({'ASC' if req.ascending else 'DESC'})"}

# ── Serve frontend with no-cache + timestamp injection ───────────────────────
FRONTEND_DIR = FilePath(__file__).resolve().parent.parent / "frontend"

@app.get("/")
async def serve_index():
    """Serve index.html with unique timestamp in script/CSS URLs to bust cache."""
    raw = (FRONTEND_DIR / "index.html").read_text(encoding="utf-8")
    ts = int(time.time() * 1000)
    # Inject timestamp into script + css URLs
    import re as _re
    raw = _re.sub(r'(script\.js)(\?[^"]*)?', f'script.js?t={ts}', raw)
    raw = _re.sub(r'(style\.css)(\?[^"]*)?', f'style.css?t={ts}', raw)
    return HTMLResponse(
        content=raw,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
        }
    )

@app.get("/{filename:path}")
async def serve_static(filename: str):
    """Serve static frontend files with no-cache headers."""
    file_path = FRONTEND_DIR / filename
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(
        file_path,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
        }
    )

