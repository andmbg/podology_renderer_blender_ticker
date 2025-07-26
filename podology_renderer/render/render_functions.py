import os
from pathlib import Path
import shelve
import subprocess
import pickle
import json

from loguru import logger

JDB = "jobs.db"


def get_jobs():
    return shelve.open(JDB, writeback=True)


def process_video(ticker_path: Path, job_id: str, frame_step: int):
    """Render and store video, put output info into JOBS dict.

    Args:
        ticker_path (str): path to the pickled Ticker object.
        job_id (str): the job ID
        frame_step (int): The step size for rendering frames.
    Returns:
        None: Only side effects (create video file, set result of job in JOBS).
    """
    logger.info(f"{job_id}: Starting video processing")
    tickerJSON_path = ticker_path.with_suffix(".json")

    try:
        # Can't use Ticker code in Blender, so use dict:
        logger.debug(f"{job_id}: Loading Ticker object from {ticker_path}")
        with open(ticker_path, "rb") as file:
            ticker = pickle.load(file)

        ticker_dict = ticker.to_dict()

        with open(tickerJSON_path, "w") as f:
            json.dump(ticker_dict, f)

        with get_jobs() as jobs:
            jobs[job_id] = {"status": "processing", "json_path": str(tickerJSON_path)}

        result = run_blender(tickerJSON_path, job_id, frame_step)

        with get_jobs() as jobs:
            jobs[job_id] = {"status": "done", "result": result}
        logger.info(f"{job_id}: Video processing completed successfully")

    except Exception as e:
        logger.error(f"{job_id}: Video processing failed: {str(e)}")

        # Create detailed error information
        error_data = {
            "error_message": str(e),
            "error_type": type(e).__name__,
            "job_id": job_id,
        }

        # If it's a RuntimeError with structured data from run_blender
        if isinstance(e, RuntimeError):
            try:
                # Try to get the structured error data
                error_args = e.args[0] if e.args else {}
                if isinstance(error_args, dict):
                    error_data.update(error_args)
                else:
                    # Fallback for string-based errors
                    error_data["error_message"] = str(error_args)
            except (IndexError, TypeError):
                pass

        with get_jobs() as jobs:
            jobs[job_id] = {"status": "failed", "error": error_data}
    finally:
        # Clean up temporary files
        if ticker_path.exists():
            ticker_path.unlink()
            logger.debug(f"Cleaned up temporary file {ticker_path}")
        if tickerJSON_path.exists():
            tickerJSON_path.unlink()
            logger.debug(f"Cleaned up Blender data file {tickerJSON_path}")


def run_blender(
    tickerJSON_path: Path,
    job_id: str,
    frame_step: int,
    blender_path="blender",
    render_script="blender_script.py",
) -> dict:
    """Call Blender to run blender_script.py for a given episode.

    This script takes the temp file path of stored timed named entities and renders
    a video, storing it in the same dir.

    Args:
        tickerJSON_path (Path): Path to the serialized Ticker object.
        job_id (str): The job ID of the rendering job.
        frame_step (int): The step size for rendering frames.
        blender_path (str): Path to the Blender executable.
        render_script (str): Path to the Blender Python script to run.
    Returns:
        dict: Result of the rendering process (stdout, stderr, video path)
    """
    logger.debug(f"Running Blender...")

    render_script_resolved = str((Path(__file__).parent / render_script).resolve())

    cmd = [
        blender_path,
        "--background",
        "--python",
        render_script_resolved,
        "--",
        str(tickerJSON_path),
        job_id,
        str(frame_step),
    ]

    env = os.environ.copy()
    env["PYTHONPATH"] = "/podology_renderer"

    logger.debug(f"Running Blender command: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)

    stdout = result.stdout
    stderr = result.stderr
    return_code = result.returncode

    logger.debug(f"Blender return code: {return_code}")
    logger.debug(f"Blender stdout: {stdout}")
    if stderr:
        logger.warning(f"Blender stderr: {stderr}")

    # Check if Blender process succeeded
    if return_code != 0:
        error_msg = f"Blender process failed with return code {return_code}"
        logger.error(f"{job_id}: {error_msg}")
        logger.error(f"{job_id}: Blender stdout: {stdout}")
        logger.error(f"{job_id}: Blender stderr: {stderr}")

        # Create a structured error that includes all the debugging info
        raise RuntimeError(
            {
                "message": error_msg,
                "return_code": return_code,
                "stdout": stdout,
                "stderr": stderr,
                "command": " ".join(cmd),
            }
        )

    # Verify the output video file was created
    video_path = f"podology_renderer/render/tmp/{Path(tickerJSON_path).stem}.mp4"
    video_path_obj = Path(video_path)

    if not video_path_obj.exists():
        error_msg = f"Blender completed but output video file not found at {video_path}"
        logger.error(f"{job_id}: {error_msg}")
        logger.error(f"{job_id}: Blender stdout: {stdout}")
        logger.error(f"{job_id}: Blender stderr: {stderr}")

        # Create a structured error for missing output file
        raise RuntimeError(
            {
                "message": error_msg,
                "return_code": return_code,
                "stdout": stdout,
                "stderr": stderr,
                "expected_path": video_path,
                "command": " ".join(cmd),
            }
        )

    logger.info(f"Video successfully created at {video_path}")
    return {
        "stdout": stdout,
        "stderr": stderr,
        "video_path": video_path,
        "return_code": return_code,
    }
