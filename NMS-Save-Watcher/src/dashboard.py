"""
Web Dashboard for Haven Watcher.
FastAPI application with Jinja2 templates for live extraction monitoring.
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .config import load_config, save_config, DEFAULT_CONFIG
from .watcher import LiveExtractionWatcher
from .database import LocalDatabase
from .api_client import APIClient

logger = logging.getLogger('nms_watcher.dashboard')

# Get paths
BASE_DIR = Path(__file__).parent.parent
TEMPLATES_DIR = BASE_DIR / 'templates'
STATIC_DIR = BASE_DIR / 'static'

# Create FastAPI app
app = FastAPI(title="Haven Watcher", docs_url=None, redoc_url=None)

# Mount static files if directory exists
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Setup templates
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Global state
_watcher: Optional[LiveExtractionWatcher] = None
_config: dict = {}
_database: Optional[LocalDatabase] = None


def get_watcher() -> Optional[LiveExtractionWatcher]:
    """Get the global watcher instance."""
    return _watcher


def set_watcher(watcher: LiveExtractionWatcher):
    """Set the global watcher instance."""
    global _watcher
    _watcher = watcher


def get_config() -> dict:
    """Get current configuration."""
    global _config
    if not _config:
        _config = load_config()
    return _config


def get_database() -> LocalDatabase:
    """Get database instance."""
    global _database
    if _database is None:
        _database = LocalDatabase()
    return _database


def format_uptime(seconds: Optional[float]) -> str:
    """Format uptime as human-readable string."""
    if not seconds:
        return "Not running"
    td = timedelta(seconds=int(seconds))
    hours, remainder = divmod(td.seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if td.days > 0:
        return f"{td.days}d {hours}h {minutes}m"
    elif hours > 0:
        return f"{hours}h {minutes}m {secs}s"
    elif minutes > 0:
        return f"{minutes}m {secs}s"
    else:
        return f"{secs}s"


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main dashboard page."""
    config = get_config()
    watcher = get_watcher()
    database = get_database()

    # Get stats
    stats = database.get_stats()
    watcher_stats = watcher.get_stats() if watcher else {}

    # Get extraction output directory
    extraction_config = config.get('live_extraction', {})
    output_dir = extraction_config.get('output_dir')
    if output_dir:
        output_path = output_dir
    else:
        output_path = str(Path.home() / "Documents" / "Haven-Extractor")

    # Check API connection
    api_connected = False
    if config.get('api', {}).get('key'):
        try:
            client = APIClient(
                config['api']['base_url'],
                config['api']['key']
            )
            api_connected, _ = client.test_connection()
        except:
            pass

    # Get recent submissions
    recent = database.get_recent_submissions(limit=5)

    # Get latest extraction
    latest_extraction = watcher.get_latest_extraction() if watcher else None

    # Add queue count to stats
    stats['queue_count'] = watcher_stats.get('queue_count', 0) if watcher else 0
    stats['live_extractions'] = watcher_stats.get('live_extractions', 0) if watcher else 0

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "config": config,
        "stats": stats,
        "watcher_stats": watcher_stats,
        "watcher_running": watcher.is_running() if watcher else False,
        "output_path": output_path,
        "uptime": format_uptime(watcher_stats.get('uptime_seconds')),
        "api_connected": api_connected,
        "recent_submissions": recent,
        "latest_extraction": latest_extraction
    })


@app.get("/history", response_class=HTMLResponse)
async def history(request: Request):
    """Submission history page."""
    config = get_config()
    watcher = get_watcher()
    database = get_database()

    submissions = database.get_recent_submissions(limit=100)
    stats = database.get_stats()

    return templates.TemplateResponse("history.html", {
        "request": request,
        "config": config,
        "submissions": submissions,
        "stats": stats,
        "watcher_running": watcher.is_running() if watcher else False
    })


@app.get("/settings", response_class=HTMLResponse)
async def settings(request: Request, message: str = None, message_type: str = None):
    """Settings page."""
    config = get_config()
    watcher = get_watcher()

    return templates.TemplateResponse("settings.html", {
        "request": request,
        "config": config,
        "watcher_running": watcher.is_running() if watcher else False,
        "message": message,
        "message_type": message_type
    })


@app.post("/settings/api")
async def save_api_settings(
    base_url: str = Form(...),
    key: str = Form("")
):
    """Save API settings."""
    global _config
    config = get_config()
    config['api']['base_url'] = base_url
    config['api']['key'] = key
    save_config(config)
    _config = config

    return RedirectResponse(
        url="/settings?message=API settings saved&message_type=success",
        status_code=303
    )


@app.post("/settings/live_extraction")
async def save_live_extraction_settings(
    output_dir: str = Form(""),
    poll_interval: float = Form(2.0)
):
    """Save live extraction settings."""
    global _config
    config = get_config()
    if 'live_extraction' not in config:
        config['live_extraction'] = {}
    config['live_extraction']['output_dir'] = output_dir if output_dir else None
    config['live_extraction']['poll_interval'] = poll_interval
    save_config(config)
    _config = config

    return RedirectResponse(
        url="/settings?message=Live extraction settings saved (restart required)&message_type=success",
        status_code=303
    )


@app.post("/settings/notifications")
async def save_notification_settings(
    request: Request
):
    """Save notification settings."""
    global _config
    form = await request.form()

    config = get_config()
    config['notifications']['enabled'] = 'enabled' in form
    config['notifications']['on_success'] = 'on_success' in form
    config['notifications']['on_duplicate'] = 'on_duplicate' in form
    config['notifications']['on_error'] = 'on_error' in form
    config['notifications']['on_offline_queue'] = 'on_offline_queue' in form
    save_config(config)
    _config = config

    return RedirectResponse(
        url="/settings?message=Notification settings saved&message_type=success",
        status_code=303
    )


@app.post("/settings/dashboard")
async def save_dashboard_settings(
    host: str = Form("127.0.0.1"),
    port: int = Form(8006)
):
    """Save dashboard settings."""
    global _config
    config = get_config()
    config['dashboard']['host'] = host
    config['dashboard']['port'] = port
    save_config(config)
    _config = config

    return RedirectResponse(
        url="/settings?message=Dashboard settings saved (restart required)&message_type=success",
        status_code=303
    )


@app.post("/settings/debug")
async def save_debug_settings(
    request: Request
):
    """Save debug settings."""
    global _config
    form = await request.form()

    config = get_config()
    config['debug']['enabled'] = 'enabled' in form
    config['debug']['log_level'] = form.get('log_level', 'INFO')
    save_config(config)
    _config = config

    return RedirectResponse(
        url="/settings?message=Debug settings saved&message_type=success",
        status_code=303
    )


@app.post("/settings/clear_history")
async def clear_history():
    """Clear submission history."""
    database = get_database()
    database.clear_old_history(days=0)  # Clear all

    return RedirectResponse(
        url="/settings?message=History cleared&message_type=success",
        status_code=303
    )


@app.post("/settings/reset")
async def reset_settings():
    """Reset settings to defaults."""
    global _config
    save_config(DEFAULT_CONFIG)
    _config = DEFAULT_CONFIG.copy()

    return RedirectResponse(
        url="/settings?message=Settings reset to defaults&message_type=success",
        status_code=303
    )


@app.get("/api/stats")
async def api_stats():
    """Get current statistics as JSON."""
    watcher = get_watcher()
    database = get_database()

    stats = database.get_stats()
    if watcher:
        watcher_stats = watcher.get_stats()
        stats.update(watcher_stats)

    return JSONResponse(stats)


@app.post("/api/start")
async def api_start():
    """Start the extraction watcher."""
    watcher = get_watcher()
    if watcher:
        watcher.start()

    return RedirectResponse(url="/", status_code=303)


@app.post("/api/stop")
async def api_stop():
    """Stop the extraction watcher."""
    watcher = get_watcher()
    if watcher:
        watcher.stop()

    return RedirectResponse(url="/", status_code=303)


@app.post("/api/process_queue")
async def api_process_queue():
    """Process queued submissions."""
    watcher = get_watcher()
    if watcher:
        results = watcher.process_queue()
        return RedirectResponse(
            url=f"/?message=Processed {len(results)} queued items",
            status_code=303
        )

    return RedirectResponse(url="/", status_code=303)


@app.post("/api/test_connection")
async def api_test_connection():
    """Test API connection."""
    config = get_config()

    if not config.get('api', {}).get('key'):
        return JSONResponse({
            "success": False,
            "message": "No API key configured"
        })

    try:
        client = APIClient(
            config['api']['base_url'],
            config['api']['key']
        )
        success, message = client.test_connection()
        return JSONResponse({
            "success": success,
            "message": message
        })
    except Exception as e:
        return JSONResponse({
            "success": False,
            "message": str(e)
        })


@app.get("/api/latest_extraction")
async def api_latest_extraction():
    """Get the latest extraction data."""
    watcher = get_watcher()
    if watcher:
        extraction = watcher.get_latest_extraction()
        if extraction:
            return JSONResponse(extraction)
    return JSONResponse({"error": "No extraction data available"})


# ============================================================
# Stats Page
# ============================================================

@app.get("/stats", response_class=HTMLResponse)
async def stats_page(request: Request):
    """Extraction statistics page."""
    config = get_config()
    watcher = get_watcher()
    database = get_database()

    # Get database stats
    db_stats = database.get_stats()

    # Get watcher stats
    watcher_stats = watcher.get_stats() if watcher else {}

    # Get latest extraction for display
    latest_extraction = watcher.get_latest_extraction() if watcher else None

    return templates.TemplateResponse("stats.html", {
        "request": request,
        "config": config,
        "watcher_running": watcher.is_running() if watcher else False,
        "db_stats": db_stats,
        "watcher_stats": watcher_stats,
        "latest_extraction": latest_extraction
    })


# ============================================================
# Queue Page - Live Extraction Queue Management
# ============================================================

@app.get("/queue", response_class=HTMLResponse)
async def queue_page(request: Request, message: str = None, message_type: str = None):
    """Upload queue management page for live extractions."""
    config = get_config()
    watcher = get_watcher()
    database = get_database()

    # Get live extraction queue from database
    pending_extractions = database.get_queued_extractions(status='pending')
    uploaded_extractions = database.get_queued_extractions(status='uploaded')
    queue_counts = database.get_queue_count()

    # Get offline queue items (legacy)
    offline_queue_items = []
    queue_path = Path(__file__).parent.parent / 'data' / 'offline_queue.json'
    if queue_path.exists():
        try:
            with open(queue_path, 'r', encoding='utf-8') as f:
                offline_queue_items = json.load(f)
        except:
            pass

    # Get unsubmitted systems from database
    unsubmitted = database.get_unsubmitted_systems(limit=50)

    return templates.TemplateResponse("queue.html", {
        "request": request,
        "config": config,
        "watcher_running": watcher.is_running() if watcher else False,
        "pending_extractions": pending_extractions,
        "uploaded_extractions": uploaded_extractions,
        "queue_counts": queue_counts,
        "queue_items": offline_queue_items,  # Legacy offline queue
        "unsubmitted": unsubmitted,
        "message": message,
        "message_type": message_type
    })


# ============================================================
# Live Extraction Queue API Endpoints
# ============================================================

@app.post("/api/queue/upload_all")
async def api_upload_all_pending():
    """Upload all pending extractions to Haven Control Room."""
    watcher = get_watcher()
    if not watcher:
        return RedirectResponse(
            url="/queue?message=Watcher not available&message_type=error",
            status_code=303
        )

    results = watcher.upload_all_pending()
    success = sum(1 for r in results if r.status.value == 'success')
    duplicate = sum(1 for r in results if r.status.value == 'duplicate')
    errors = sum(1 for r in results if r.status.value == 'error')

    msg = f"Uploaded: {success} success, {duplicate} duplicate, {errors} errors"
    msg_type = "success" if errors == 0 else "warning"

    return RedirectResponse(
        url=f"/queue?message={msg}&message_type={msg_type}",
        status_code=303
    )


@app.post("/api/queue/upload/{glyph_code}")
async def api_upload_single(glyph_code: str, galaxy: str = "Euclid"):
    """Upload a specific extraction to Haven Control Room."""
    watcher = get_watcher()
    if not watcher:
        return RedirectResponse(
            url="/queue?message=Watcher not available&message_type=error",
            status_code=303
        )

    result = watcher.upload_queued(glyph_code, galaxy)

    msg = f"{result.system_name or glyph_code}: {result.message}"
    msg_type = "success" if result.status.value == 'success' else (
        "warning" if result.status.value == 'duplicate' else "error"
    )

    return RedirectResponse(
        url=f"/queue?message={msg}&message_type={msg_type}",
        status_code=303
    )


@app.post("/api/queue/remove/{glyph_code}")
async def api_remove_from_queue(glyph_code: str, galaxy: str = "Euclid"):
    """Remove a specific extraction from queue without uploading."""
    watcher = get_watcher()
    database = get_database()

    # Try via watcher first, then direct database
    if watcher:
        watcher.remove_from_queue(glyph_code, galaxy)
    else:
        database.remove_queued_extraction(glyph_code, galaxy)

    return RedirectResponse(
        url="/queue?message=Removed from queue&message_type=success",
        status_code=303
    )


@app.post("/api/queue/clear_uploaded")
async def api_clear_uploaded():
    """Clear all successfully uploaded extractions from the queue."""
    watcher = get_watcher()
    database = get_database()

    if watcher:
        count = watcher.clear_uploaded()
    else:
        count = database.clear_uploaded_queue()

    return RedirectResponse(
        url=f"/queue?message=Cleared {count} uploaded items&message_type=success",
        status_code=303
    )


@app.get("/api/queue/pending")
async def api_get_pending_queue():
    """Get pending extractions as JSON."""
    database = get_database()
    pending = database.get_queued_extractions(status='pending')
    return JSONResponse(pending)


@app.get("/api/queue/counts")
async def api_get_queue_counts():
    """Get queue counts as JSON."""
    database = get_database()
    counts = database.get_queue_count()
    return JSONResponse(counts)


# ============================================================
# Legacy Offline Queue (for backwards compatibility)
# ============================================================

@app.post("/api/clear_queue")
async def api_clear_queue():
    """Clear the legacy offline queue."""
    queue_path = Path(__file__).parent.parent / 'data' / 'offline_queue.json'
    if queue_path.exists():
        with open(queue_path, 'w', encoding='utf-8') as f:
            json.dump([], f)

    return RedirectResponse(url="/queue?message=Legacy queue cleared&message_type=success", status_code=303)


@app.post("/api/queue/{index}/retry")
async def api_queue_retry(index: int):
    """Retry a specific queued item (legacy)."""
    watcher = get_watcher()
    if watcher:
        results = watcher.process_queue()
        return RedirectResponse(
            url=f"/queue?message=Processed {len(results)} items&message_type=success",
            status_code=303
        )
    return RedirectResponse(url="/queue", status_code=303)


@app.post("/api/queue/{index}/remove")
async def api_queue_remove(index: int):
    """Remove a specific item from the legacy queue."""
    queue_path = Path(__file__).parent.parent / 'data' / 'offline_queue.json'
    if queue_path.exists():
        try:
            with open(queue_path, 'r', encoding='utf-8') as f:
                queue_items = json.load(f)

            if 0 <= index < len(queue_items):
                queue_items.pop(index)

                with open(queue_path, 'w', encoding='utf-8') as f:
                    json.dump(queue_items, f, indent=2)

        except:
            pass

    return RedirectResponse(url="/queue?message=Removed from queue&message_type=success", status_code=303)


@app.post("/api/reset_failed")
async def api_reset_failed():
    """Reset all failed submissions so they can be retried on next save."""
    database = get_database()
    count = database.reset_all_failed_for_retry()
    return RedirectResponse(
        url=f"/queue?message=Reset {count} failed submissions for retry",
        status_code=303
    )


@app.post("/api/unsubmitted/{system_id}/reset")
async def api_reset_unsubmitted(system_id: int):
    """Reset a specific unsubmitted system for retry."""
    database = get_database()

    # Get the system info first
    with database._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT glyph_code, galaxy FROM processed_systems WHERE id = ?', (system_id,))
        row = cursor.fetchone()
        if row:
            database.reset_failed_for_retry(row['glyph_code'], row['galaxy'])

    return RedirectResponse(url="/queue?message=System reset for retry", status_code=303)


def run_dashboard(config: dict, watcher: LiveExtractionWatcher):
    """
    Run the dashboard server.

    Args:
        config: Configuration dictionary
        watcher: LiveExtractionWatcher instance
    """
    import uvicorn

    global _config
    _config = config

    set_watcher(watcher)

    host = config.get('dashboard', {}).get('host', '127.0.0.1')
    port = config.get('dashboard', {}).get('port', 8006)

    logger.info(f"Starting dashboard at http://{host}:{port}")

    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="warning"
    )
