import json
from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel

from .pipeline import run_pipeline

app = FastAPI()


@app.get("/health")
def health_check():
    return {"status": "ok"}


class GenerateRequest(BaseModel):
    brief_path: str
    count: int = 5


class GenerateResponse(BaseModel):
    output_dir: str
    variant_count: int


@app.post("/generate")
def generate(request: GenerateRequest):
    output_dir = run_pipeline(request.brief_path, count=request.count)

    with open(Path(output_dir) / "manifest.json") as f:
        manifest = json.load(f)

    return GenerateResponse(
        output_dir=str(output_dir),
        variant_count=manifest["variant_count"],
    )