from typing import Any

from fastapi import FastAPI


app = FastAPI(
    title="AIOps Incident API",
    version="0.1.0",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "healthy"}


@app.post("/alerts")
def receive_alert(payload: dict[str, Any]) -> dict[str, str]:
    return {
        "status": "received",
        "alerts": str(len(payload.get("alerts", []))),
    }
