"""FastAPI application entrypoint."""

from fastapi import FastAPI

app = FastAPI(
    title="Data Cleaning Tool",
    description="Deal revenue grid cleaning API",
    version="0.1.0",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
