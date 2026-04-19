# Automated EDA & Data Engineering Platform - Context Summary

## Project Objective
The goal was to migrate an MVP Data Engineering Platform (originally built with Pandas with a 10,000 row limit) into a highly scalable, production-ready enterprise application capable of handling Big Data.

## Key Decisions & Context
1. **Migration to Polars:** We completely replaced `pandas` with `polars` in `eda_engine.py`. Polars is written in Rust and uses lazy evaluation, allowing us to drop the 10,000-row limit and process massive datasets instantly.
2. **Session Architecture:** To support multiple concurrent users (crucial for future deployment/SaaS), we implemented a UUID-based session manager. Uploaded datasets are converted into `.parquet` files stored locally under `/sessions/`, preventing memory collisions.
3. **AI Context Optimization:** Instead of sending the full dataset to the local AI (LM Studio), we implemented "Smart Chunking", sending only the statistical audit data (specifically Dangers/Warnings) so the AI provides high-quality insights without blowing up the token context window.
4. **Lazy Visualization Loading:** We utilized the `IntersectionObserver` API in the frontend. Charts are only rendered via API calls when the user scrolls to them, preserving browser memory.
5. **Security Implementations:**
   - **Path Traversal Protection:** Implemented regex UUID validation in the backend.
   - **PII Scrubbing:** Added an automated regex scrubber during dataset upload to redact emails, phone numbers, and sensitive columns before AI analysis.
   - **XSS Sanitization:** Added a frontend HTML sanitizer to prevent malicious script injection if the AI hallucinates.

## How to Resume Work
If you resume work on this project with me (or another AI agent), provide them this context file so they understand the architectural decisions made:
- We use **Polars** for backend data processing.
- We use **FastAPI** for routing.
- We use **Vanilla JS/CSS** for the frontend with CSS custom properties for Light/Dark themes.
- We use an **AbortController** to stop AI generation streams.
