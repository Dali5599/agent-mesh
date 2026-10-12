from fastapi import FastAPI, HTTPException, status
from typing import Dict, Any, List
from agent_mesh.domain.models import MeshHealthStatus

def create_app(orchestrator: Any = None) -> FastAPI:
    app = FastAPI(title="Agent Mesh API", version="0.1.0")

    @app.get("/health")
    async def health():
        return {"status": "healthy", "version": "0.1.0"}

    @app.get("/metrics")
    async def metrics():
        return {"total_requests": 0, "active_circuits": 0, "mesh_uptime_seconds": 10.0}

    @app.get("/api/v1/agents")
    async def list_agents():
        return []

    @app.post("/api/v1/dispatch")
    async def dispatch(payload: Dict[str, Any]):
        if "sender_id" not in payload or "receiver_id" not in payload:
            raise HTTPException(status_code=422, detail="Missing sender_id or receiver_id")
        return {"status": "dispatched"}

    @app.get("/api/v1/resilience/circuit-breakers")
    async def get_circuits():
        return []

    @app.get("/api/v1/resilience/rate-limiters")
    async def get_limiters():
        return []

    return app

app = create_app()
