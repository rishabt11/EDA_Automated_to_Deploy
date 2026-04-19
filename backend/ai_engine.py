"""
AI Engine — Supports both Groq (Cloud/Free) and LM Studio (Local).
Configure via environment variables:
  AI_PROVIDER=groq       → Uses Groq Cloud (free tier)
  AI_PROVIDER=lmstudio   → Uses local LM Studio server
"""
import os
import json
import polars as pl

AI_PROVIDER = os.getenv("AI_PROVIDER", "groq").lower()

# --- Groq Setup ---
if AI_PROVIDER == "groq":
    from groq import AsyncGroq
    client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY", ""))
    MODEL_NAME = "llama-3.3-70b-versatile"
else:
    # --- LM Studio Setup ---
    from openai import AsyncOpenAI
    client = AsyncOpenAI(
        base_url=os.getenv("LMSTUDIO_URL", "http://127.0.0.1:1234/v1"),
        api_key="lm-studio"
    )
    MODEL_NAME = "local-model"


async def generate_initial_report(data_context: str, stats: dict, audit: list, shape: list):
    """Stream an initial EDA strategy report."""
    
    # Smart Context Chunking: only send critical audit issues
    critical_items = [item for item in audit if 'Null' in str(item.get('severity', '')) or 'Skew' in str(item.get('severity', ''))]
    audit_summary = json.dumps(critical_items[:15], indent=2) if critical_items else "No critical issues found."
    
    system_prompt = f"""You are a Senior AI Engineer and Data Analyst.
The user uploaded a dataset with shape: {shape[0]} rows x {shape[1]} columns.
Business context: {data_context}

Here are the critical data quality issues found:
{audit_summary}

Generate a comprehensive EDA Strategy Report covering:
1. Data Quality Assessment
2. Key Statistical Insights
3. Recommended Feature Engineering steps
4. Suggested ML approach for this problem
Keep it concise and actionable."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "Generate the EDA Strategy Report for this dataset."}
    ]

    try:
        stream = await client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            stream=True,
            temperature=0.7,
            max_tokens=2048
        )
        
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    except Exception as e:
        yield f"\n\n[AI Error: {str(e)}]"


async def chat_with_data(message: str, history: list, data_context: str, df: pl.DataFrame):
    """Stream a chat response about the dataset."""
    
    shape = df.shape
    columns = df.columns
    sample = df.head(3).to_pandas().to_string()
    
    system_prompt = f"""You are a Senior AI Engineer and Data Analyst.
The user is working with a dataset: {shape[0]} rows x {shape[1]} columns.
Columns: {columns}
Business context: {data_context}

Sample data:
{sample}

Provide concise, actionable Python/Polars/Pandas answers based on this context."""

    messages = [{"role": "system", "content": system_prompt}]
    
    # Add history (limit to last 10 messages)
    for item in history[-10:]:
        if isinstance(item, dict):
            role = item.get("role", "user")
            content = item.get("content", "")
            if content:
                messages.append({"role": role, "content": content})
    
    messages.append({"role": "user", "content": message})

    try:
        stream = await client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            stream=True,
            temperature=0.7,
            max_tokens=1024
        )

        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    except Exception as e:
        yield f"\n\n[AI Error: {str(e)}]"
