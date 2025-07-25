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


def process_video(ticker_path: str, job_id: str, frame_step: int = 10):
    """Render and store video, put output info into JOBS dict.

    Args:
        ticker_path (str): path to the temp file with pickled ticker.
        job_id (str): the job ID
        frame_step (int): The step size for rendering frames (default is 10).
    Returns:
        None: Only side effects (create video file, set result of job in JOBS).
    """
    ticker_path_obj = Path(ticker_path)
    try:
        logger.info(f"{job_id}: Starting video processing")
        
        # Load the ticker object and convert it to a simple dict for Blender
        logger.debug(f"{job_id}: Loading ticker from {ticker_path}")
        ticker = json.load(ticker_path_obj.open("rb"))
        
        # Use the ticker's built-in to_dict() method
        logger.debug(f"{job_id}: Converting ticker to dict using .to_dict()")
        ticker_dict = ticker.to_dict()
        
        # Save the simplified data for Blender
        tickerdict_path = ticker_path_obj.with_suffix(".blender.pkl")
        logger.debug(f"{job_id}: Saving Blender data to {tickerdict_path}")
        with open(tickerdict_path, "wb") as f:
            pickle.dump(ticker_dict, f)
        
        result = run_blender(tickerdict_path, job_id, frame_step)
        with shelve.open(JDB, writeback=True) as jobs:
            jobs[job_id] = {"status": "done", "result": result}
        logger.info(f"{job_id}: Video processing completed successfully")
        
        # Clean up the Blender data file
        if tickerdict_path.exists():
            tickerdict_path.unlink()
            logger.debug(f"{job_id}: Cleaned up Blender data file {tickerdict_path}")
            
    except Exception as e:
        logger.error(f"{job_id}: Video processing failed: {str(e)}")
        
        # Create detailed error information
        error_data = {
            "error_message": str(e),
            "error_type": type(e).__name__,
            "job_id": job_id
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
        # Clean up the temporary ticker file
        if ticker_path_obj.exists():
            ticker_path_obj.unlink()
            logger.debug(f"{job_id}: Cleaned up temporary file {ticker_path}")


def run_blender(
    ticker_path: Path,
    job_id: str,
    frame_step: int,
    blender_path="blender",
    render_script="blender_script.py",
) -> dict:
    """Call Blender to run blender_script.py for a given episode.

    This script takes the temp file path of stored timed named entities and renders
    a video, storing it in the same dir.

    Args:
        ticker_path (Path): Path to the temp file with pickled ticker.
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
        ticker_path,
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

    logger.info(f"Blender return code: {return_code}")
    logger.info(f"Blender stdout: {stdout}")
    if stderr:
        logger.warning(f"Blender stderr: {stderr}")

    # Check if Blender process succeeded
    if return_code != 0:
        error_msg = f"Blender process failed with return code {return_code}"
        logger.error(f"{job_id}: {error_msg}")
        logger.error(f"{job_id}: Blender stdout: {stdout}")
        logger.error(f"{job_id}: Blender stderr: {stderr}")
        
        # Create a structured error that includes all the debugging info
        raise RuntimeError({
            "message": error_msg,
            "return_code": return_code,
            "stdout": stdout,
            "stderr": stderr,
            "command": ' '.join(cmd)
        })

    # Verify the output video file was created
    video_path = f"podology_renderer/render/tmp/{Path(ticker_path).stem}.mp4"
    video_path_obj = Path(video_path)
    
    if not video_path_obj.exists():
        error_msg = f"Blender completed but output video file not found at {video_path}"
        logger.error(f"{job_id}: {error_msg}")
        logger.error(f"{job_id}: Blender stdout: {stdout}")
        logger.error(f"{job_id}: Blender stderr: {stderr}")
        
        # Create a structured error for missing output file
        raise RuntimeError({
            "message": error_msg,
            "return_code": return_code,
            "stdout": stdout,
            "stderr": stderr,
            "expected_path": video_path,
            "command": ' '.join(cmd)
        })

    logger.info(f"Video successfully created at {video_path}")
    return {
        "stdout": stdout,
        "stderr": stderr,
        "video_path": video_path,
        "return_code": return_code,
    }
