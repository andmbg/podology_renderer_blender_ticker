import os
from pathlib import Path
import shelve
import subprocess

from loguru import logger

JDB = "jobs.db"


def get_jobs():
    return shelve.open(JDB, writeback=True)


def process_video(ticker_path: str, job_id: str, frame_step: int = 10):
    """Render and store video, put output info into JOBS dict.

    Args:
        ticker_path (str): path to the temp file with pickled ticker.
        job_id (str): the job ID
        frame_step (int): The step size for rendering frames (default is 10).
    Returns:
        None: Only side effects (create video file, set result of job in JOBS).
    """
    try:
        result = run_blender(ticker_path, job_id, frame_step)
        with shelve.open(JDB, writeback=True) as jobs:
            jobs[job_id] = {"status": "done", "result": result}
    except Exception as e:
        with get_jobs() as jobs:
            jobs[job_id] = {"status": "failed", "error": str(e)}
    finally:
        ticker_path.unlink(missing_ok=True)


def run_blender(
    ticker_path: str,
    job_id: str,
    frame_step: int,
    blender_path="/usr/bin/blender",
    render_script="blender_script.py",
) -> dict:
    """Call Blender to run blender_script.py for a given episode.

    This script takes the temp file path of stored timed named entities and renders
    a video, storing it in the same dir.

    Args:
        naments_path (str): path to temp file with pickled ticker.
        blender_path (str): Path to the Blender executable.
        render_script (str): Path to the Blender Python script to run.
    Returns:
        dict: Result of the rendering process (stdout, stderr, video path)
    """
    logger.debug(f"Running Blender...")

    render_script_resolved = str((Path(__file__).parent / render_script).resolve())

    cmd = [
        "xvfb-run",
        "-a",
        blender_path,
        "--background",
        "--python",
        render_script_resolved,
        "--",
        ticker_path,
        job_id,
        str(frame_step),
    ]

    env = os.environ.copy()
    env["PYTHONPATH"] = "/podology_renderer"
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)
    stdout = result.stdout
    stderr = result.stderr

    logger.info(f"Blender stdout: {stdout}")
    logger.info(f"Blender stderr: {stderr}")

    return {
        "stdout": stdout,
        "stderr": stderr,
        "video_path": f"{ticker_path.stem}.mp4",
    }
