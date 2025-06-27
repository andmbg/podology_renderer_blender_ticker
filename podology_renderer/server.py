import json
import os
import pickle
import sys
import secrets
from pathlib import Path
import shelve

import uvicorn
from loguru import logger
from dotenv import load_dotenv, find_dotenv
from fastapi.responses import FileResponse
from fastapi import (
    FastAPI,
    HTTPException,
    BackgroundTasks,
    Request,
    Depends,
)
from pydantic import BaseModel

from podology_renderer.render.render_functions import process_video, get_jobs
from podology_renderer.render.wordticker import ticker_from_timed_naments

logger.remove()
logger.add(sys.stderr, level="DEBUG")

load_dotenv(find_dotenv())

API_TOKEN = os.getenv("API_TOKEN")
UPLOAD_DIR = Path("/tmp/audio_files")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Create the FastAPI app
app = FastAPI()


class RenderRequest(BaseModel):
    naments: str
    frame_step: int = 10


def generate_job_id(length=8):
    # Generates a random 8-character hex string
    return f"jid_{secrets.token_hex(length // 2)}"


def check_api_token(request: Request):
    logger.info("Checking API token for request")
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")
    token = auth.split(" ")[1]
    if token != API_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid API token")


@app.post("/render")
async def render(
    req: RenderRequest,
    background_tasks: BackgroundTasks = None,
    request: Request = None,
    _: None = Depends(check_api_token),
):
    """The rendering endpoint.

    Handles uploads of timed named entity data to produce a scroll video.
    Expects a JSON string in the format:

        [
            ["token" {str}, timestamp {float}],
            ...
        ]

    ...and optionally a frame step parameter to control the rendering speed
    (useful for faster testing).

    Args:
        naments (str): A JSON string containing named entities with timestamps.
        frame_step (int): The step size for rendering frames (default is 10).

    Returns:
        A JSON response with a job ID for tracking the rendering process.
    """

    naments = json.loads(req.naments)
    naments = [(token, float(timestamp)) for timestamp, token in naments]
    frame_step = req.frame_step

    job_id = generate_job_id()
    logger.info(f"{job_id}: Received a render request")
    with get_jobs() as JOBS:
        JOBS[job_id] = {"status": "processing", "result": None}

    # Prepare the ticker object:
    ticker = ticker_from_timed_naments(naments)
    ticker_path = Path(f"podology_renderer/render/tmp/{job_id}.pickle")
    with open(ticker_path, "wb") as f:
        pickle.dump(ticker, f)

    # Start rendering background task with reference to the stored ticker:
    background_tasks.add_task(
        process_video, ticker_path=ticker_path, job_id=job_id, frame_step=frame_step
    )

    return {"job_id": job_id}


@app.get("/status/{job_id}")
def get_status(
    job_id: str,
    request: Request = None,
    _: None = Depends(check_api_token),
):
    logger.debug(f"Checking status for job {job_id}")
    with get_jobs() as JOBS:
        job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return {"status": job["status"]}


@app.get("/result/{job_id}")
def get_result(
    job_id: str,
    request: Request = None,
    _: None = Depends(check_api_token),
):
    with get_jobs() as JOBS:
        job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["status"] != "done":
        raise HTTPException(status_code=202, detail="Transcription not finished")

    result = job["result"]
    video_path = Path(result["video_path"])
    if not video_path or not video_path.exists():
        raise HTTPException(status_code=404, detail="Video file not found")

    logger.debug(f"Sending out video file: {video_path}")
    return FileResponse(
        video_path,
        media_type="video/mp4",
        filename=video_path.name,
    )


@app.get("/")
def root():
    """
    Root endpoint to verify the server is running.
    """
    return {"message": "Podology Renderer API is running"}


if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8002)
