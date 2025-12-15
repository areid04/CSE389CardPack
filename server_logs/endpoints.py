from fastapi import APIRouter, Query
from pathlib import Path

router = APIRouter(prefix="/admin/logs", tags=["logs"])

LOG_DIR = Path("logs")

def get_log_path(log_type: str) -> Path:
    return LOG_DIR / f"{log_type}.log"

@router.get("/tail")
async def tail_logs(
    log_type: str = Query("server", regex="^(server|auction|marketplace)$"),
    lines: int = Query(50, le=500)
):
    """Get last N lines (like tail command)"""
    log_path = get_log_path(log_type)
    if not log_path.exists():
        return {"lines": [], "error": f"No {log_type} log file"}
    
    with open(log_path) as f:
        all_lines = f.readlines()
    return {"lines": all_lines[-lines:], "count": len(all_lines), "log_type": log_type}

@router.get("/head")
async def head_logs(
    log_type: str = Query("server", regex="^(server|auction|marketplace)$"),
    lines: int = Query(50, le=500)
):
    """Get first N lines (like head command)"""
    log_path = get_log_path(log_type)
    if not log_path.exists():
        return {"lines": [], "error": f"No {log_type} log file"}
    
    with open(log_path) as f:
        result = []
        for i, line in enumerate(f):
            if i >= lines:
                break
            result.append(line)
    return {"lines": result, "log_type": log_type}

@router.get("/search")
async def search_logs(
    log_type: str = Query("server", regex="^(server|auction|marketplace)$"),
    level: str = None,
    contains: str = None,
    limit: int = Query(100, le=1000)
):
    """Search/filter logs"""
    log_path = get_log_path(log_type)
    if not log_path.exists():
        return {"lines": [], "error": f"No {log_type} log file"}
    
    results = []
    with open(log_path) as f:
        for line in f:
            if level and f'"level": "{level}"' not in line:
                continue
            if contains and contains.lower() not in line.lower():
                continue
            results.append(line.strip())
            if len(results) >= limit:
                break
    
    return {"lines": results, "count": len(results), "log_type": log_type}

@router.get("/available")
async def list_available_logs():
    """List all available log files"""
    if not LOG_DIR.exists():
        return {"logs": []}
    
    logs = [f.stem for f in LOG_DIR.glob("*.log")]
    return {"logs": logs}