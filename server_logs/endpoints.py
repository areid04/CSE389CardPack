from fastapi import APIRouter, Query
from pathlib import Path
import re

router = APIRouter(prefix="/admin/logs", tags=["logs"])

LOG_PATH = Path("logs/server.log")

@router.get("/tail")
async def tail_logs(lines: int = Query(50, le=500)):
    """Get last N lines (like tail command)"""
    if not LOG_PATH.exists():
        return {"lines": [], "error": "No log file"}
    
    with open(LOG_PATH) as f:
        all_lines = f.readlines()
    return {"lines": all_lines[-lines:], "count": len(all_lines)}

@router.get("/head")
async def head_logs(lines: int = Query(50, le=500)):
    """Get first N lines (like head command)"""
    if not LOG_PATH.exists():
        return {"lines": [], "error": "No log file"}
    
    with open(LOG_PATH) as f:
        return {"lines": [next(f) for _ in range(lines) if f]}

@router.get("/search")
async def search_logs(
    level: str = None,
    contains: str = None,
    limit: int = Query(100, le=1000)
):
    """Search/filter logs"""
    if not LOG_PATH.exists():
        return {"lines": []}
    
    results = []
    with open(LOG_PATH) as f:
        for line in f:
            if level and f"] {level} " not in line:
                continue
            if contains and contains.lower() not in line.lower():
                continue
            results.append(line.strip())
            if len(results) >= limit:
                break
    
    return {"lines": results, "count": len(results)}