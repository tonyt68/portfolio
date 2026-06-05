import os
import logging
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import json

logging.basicConfig(level=os.getenv('LOG_LEVEL', 'INFO'))
log = logging.getLogger(__name__)

app = FastAPI(title="A2A Trust PoC Demo", version="0.1.0")

# Serve static files (CSS, JS)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/health")
async def health_check():
    """Health check"""
    return {"status": "healthy", "service": "demo_web"}


@app.get("/")
async def index():
    """Serve demo.html"""
    return FileResponse("demo.html", media_type="text/html")


@app.get("/prep")
async def prep():
    """Serve prep.html"""
    return FileResponse("prep.html", media_type="text/html")


@app.get("/api/config")
async def get_config():
    """Get demo configuration"""
    return {
        "mcp_url": os.getenv("MCP_URL", "http://localhost:8001"),
        "admin_url": os.getenv("ADMIN_URL", "http://localhost:8002"),
        "demo_port": os.getenv("DEMO_PORT", 8765),
        "scenarios": 11
    }


@app.post("/api/scenario/run")
async def run_scenario(scenario: dict):
    """Run a demo scenario"""
    try:
        scenario_id = scenario.get("id")
        log.info(f"Running scenario {scenario_id}")

        # TODO: Implement scenario runner
        return {
            "status": "success",
            "scenario_id": scenario_id,
            "result": "pending"
        }

    except Exception as e:
        log.error(f"Scenario error: {e}")
        return {"status": "error", "message": str(e)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8765)
