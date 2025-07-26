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
JDB = "jobs.db"

# Create the FastAPI app
app = FastAPI()


class RenderRequest(BaseModel):
    naments: str
    job_id: str
    frame_step: int = 10


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

    job_id = req.job_id
    logger.info(f"{job_id}: Received a render request")
    with get_jobs() as JOBS:
        JOBS[job_id] = {"status": "processing"}

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

    if job["status"] == "processing":
        logger.debug(f"Job {job_id} is still processing")
        return {"status": "processing"}

    if job["status"] == "done":
        logger.debug(f"Job {job_id} is done")
        return {"status": "done"}

    if job["status"] == "failed":
        logger.debug(f"Job {job_id} failed")
        error_detail = job.get("error", "Unknown error")
        return {"status": "failed", "error": error_detail}

    return {"status": job["status"]}


@app.get("/debug/{job_id}")
def get_debug_info(
    job_id: str,
    request: Request = None,
    _: None = Depends(check_api_token),
):
    """Get detailed debugging information for a job, including full Blender output."""
    logger.debug(f"Getting debug info for job {job_id}")
    with get_jobs() as JOBS:
        job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Return the complete job data for debugging
    debug_info = {"job_id": job_id, "status": job["status"], "full_job_data": job}

    # Add system information
    debug_info["system_info"] = {
        "cwd": os.getcwd(),
        "python_path": sys.path[:3],  # First few entries
        "environment_vars": {
            k: v
            for k, v in os.environ.items()
            if k.startswith(("API_", "HF_", "PYTHONPATH", "PATH"))
        },
    }

    return debug_info


@app.get("/result/{job_id}")
def get_result(
    job_id: str,
    request: Request = None,
    _: None = Depends(check_api_token),
):
    with shelve.open(JDB, writeback=True) as JOBS:
        job = JOBS.get(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job["status"] == "failed":
        error_detail = job.get("error", "Unknown error")
        # If error is a dict, format it nicely for the response
        if isinstance(error_detail, dict):
            error_msg = error_detail.get("error_message", "Unknown error")
            if "stdout" in error_detail or "stderr" in error_detail:
                error_msg += f" (Use /debug/{job_id} endpoint for full Blender output)"
        else:
            error_msg = str(error_detail)
        raise HTTPException(status_code=400, detail=f"Job failed: {error_msg}")

    if job["status"] != "done":
        raise HTTPException(status_code=400, detail="Job is not done yet")

    if "result" not in job or "video_path" not in job["result"]:
        raise HTTPException(
            status_code=500, detail="Job marked as done but result data is missing"
        )

    # Get the video path from the job result
    video_path = Path(job["result"]["video_path"])

    if not video_path.exists():
        detail = f"Video file not found. path: {str(video_path)}; cwd: {os.getcwd()}; job_result: {job.get('result', {})}"
        logger.error(f"Job {job_id}: {detail}")
        raise HTTPException(status_code=404, detail=detail)

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
