from fastapi import FastAPI

from app.config import settings


app = FastAPI(
    title="AIOps Incident Assistant",
    version="0.1.0",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "healthy",
        "environment": settings.app_env,
    }
