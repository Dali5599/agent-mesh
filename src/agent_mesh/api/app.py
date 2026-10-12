import time
import uuid
from typing import Callable
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from agent_mesh.api.routes import agents, router as api_router
from agent_mesh.telemetry.tracer import get_tracer

tracer = get_tracer("agent_mesh.api")


def create_app() -> FastAPI:
    """Application factory for the Agent Mesh FastAPI control and data plane gateway."""
    app = FastAPI(
        title="Agent Mesh API",
        description="High-Performance Distributed Service Mesh for AI Agent Swarms - API Gateway",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def telemetry_and_request_id_middleware(request: Request, call_next: Callable) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        start_time = time.perf_counter()

        with tracer.start_as_current_span(f"HTTP {request.method} {request.url.path}") as span:
            span.set_attribute("http.method", request.method)
            span.set_attribute("http.url", str(request.url))
            span.set_attribute("http.request_id", request_id)

            try:
                response = await call_next(request)
                process_time = time.perf_counter() - start_time
                
                response.headers["X-Request-ID"] = request_id
                response.headers["X-Process-Time"] = f"{process_time:.4f}"

                span.set_attribute("http.status_code", response.status_code)
                span.set_attribute("http.process_time", process_time)

                return response
            except Exception as exc:
                process_time = time.perf_counter() - start_time
                span.record_exception(exc)
                span.set_attribute("http.status_code", 500)
                span.set_attribute("http.process_time", process_time)

                error_content = {
                    "error": {
                        "code": "INTERNAL_SERVER_ERROR",
                        "message": str(exc),
                        "request_id": request_id,
                    }
                }
                return JSONResponse(
                    status_code=500,
                    content=error_content,
                    headers={
                        "X-Request-ID": request_id,
                        "X-Process-Time": f"{process_time:.4f}",
                    },
                )

    app.include_router(api_router, prefix="/api/v1")
    app.include_router(agents.router, prefix="/api/v1")

    @app.get("/healthz", tags=["Monitoring"])
    async def health_check() -> dict:
        """Health check endpoint for liveness probes."""
        return {"status": "healthy", "service": "agent-mesh-api"}

    @app.get("/readyz", tags=["Monitoring"])
    async def readiness_check() -> dict:
        """Readiness check endpoint for traffic routing."""
        return {"status": "ready", "service": "agent-mesh-api"}

    return app


app = create_app()
