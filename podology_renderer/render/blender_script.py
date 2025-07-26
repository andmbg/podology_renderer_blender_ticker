import os
import sys
import bpy
import json

print(f"Blender script starting...")
print(f"Python executable: {sys.executable}")
print(f"Working directory: {os.getcwd()}")

#
# File loading
#
canvas_path = "podology_renderer/render/canvas.blend"

# Process command line arguments (the pickle file path):
args = sys.argv
print(f"All arguments: {args}")

if "--" in args:
    args = args[args.index("--") + 1:]
else:
    raise ValueError("No arguments provided.")

if len(args) != 3:
    raise ValueError("Expected 3 arguments: ticker pickle path, job ID, frame step.")

ticker_path, job_id, frame_step = args
print(f"Ticker path: {ticker_path}")
print(f"Job ID: {job_id}")
print(f"Frame step: {frame_step}")

if not os.path.exists(ticker_path):
    raise FileNotFoundError(f"Ticker file not found: {ticker_path}")

with open(ticker_path, "rb") as file:
    ticker = json.load(file)

print(f"Ticker loaded: {ticker}")

#
# Implement the Appearance.frame() method logic
#
def appearance_frame(appearance_data, t):
    """
    Implement the Appearance.frame() method logic.
    Returns the envelope value at time t.
    """
    start = appearance_data['start']
    end = appearance_data['end']
    
    if t <= start:
        return 0.0
    elif end <= t:
        return 1.0
    else:
        # Linear interpolation between start and end:
        return (t - start) / (end - start)

#
# Implement the Ticker.get_value() method logic
#
def get_value(ticker_data, apid, t):
    """
    Implement the Ticker.get_value() method logic.
    Search for the appearance by apid and return its frame value at time t.
    """
    for lane in ticker_data['lanes']:
        for appearance in lane:
            if appearance['apid'] == apid:
                return appearance_frame(appearance, t)
    return 0.0

#
# Render preparations
#

# Load the prepared .blend file
if not os.path.exists(canvas_path):
    raise FileNotFoundError(f"Canvas file not found: {canvas_path}")

print(f"Loading canvas file: {canvas_path}")
bpy.ops.wm.open_mainfile(filepath=canvas_path)

print(f"Opened canvas file: {canvas_path}")

#
# EEVEE
#
bpy.data.scenes["Scene"].render.engine = "BLENDER_EEVEE"

# Verify/Set render output to video (if not already configured in the .blend file)
bpy.context.scene.render.filepath = f"podology_renderer/render/tmp/{job_id}.mp4"
bpy.context.scene.render.image_settings.file_format = "FFMPEG"
bpy.context.scene.render.ffmpeg.format = "MPEG4"  # H.264 MP4
bpy.data.scenes["Scene"].render.fps = ticker['fps']
bpy.data.scenes["Scene"].frame_step = int(frame_step)

# Remove this line since we're using EEVEE, not Cycles
# bpy.data.scenes["Scene"].cycles.device = "GPU"

lane_spacing = 1.5
bpy.context.scene.frame_end = int(ticker['end'] * ticker['fps'])

#
# Create text objects
#

# First, check existence of the shared material:
print("Checking for 'word_material'...")
print(f"Available materials: {list(bpy.data.materials.keys())}")

if "word_material" not in bpy.data.materials:
    raise ValueError("Material 'word_material' not found in the .blend file.")
else:
    mat = bpy.data.materials["word_material"]
    print(f"Found material 'word_material': {mat}")

print(f"Creating text objects for {len(ticker['lanes'])} lanes...")

# Create the objects:
for lane_idx, lane in enumerate(ticker["lanes"]):
    y_loc = lane_idx * lane_spacing
    print(f"Processing lane {lane_idx} with {len(lane)} appearances")
    
    for appearance in lane:
        # Create the text object
        bpy.ops.object.text_add(location=(0, y_loc, 0))
        text_obj = bpy.context.object
        text_obj.data.body = appearance["term"]

        text_obj.name = appearance['apid']
        text_obj["value"] = 0.0
    
        if text_obj.data.materials:
            text_obj.data.materials[0] = mat
        else:
            text_obj.data.materials.append(mat)
        
        print(f"Created text object '{text_obj.name}' with text '{appearance['term']}'")

#
# Add a handler that updates the values of the text objects upon frame change;
# Also inserts keyframes at each frame, as this is necessary for headless rendering.
#
def update_values(scene):
    current_frame = scene.frame_current
    for obj in bpy.data.objects:
        if "value" in obj:
            t = current_frame / ticker['fps']
            val = get_value(ticker, obj.name, t)  # Use our implemented get_value function
            obj["value"] = val
            obj.location.x = obj["value"] * (-22)
            
            # Insert keyframes for animation
            obj.keyframe_insert(data_path="location", frame=current_frame, index=0)  # x location
            obj.keyframe_insert(data_path='["value"]', frame=current_frame)

bpy.app.handlers.frame_change_post.clear()  # Clear existing handlers if needed
bpy.app.handlers.frame_change_post.append(update_values)

#
# Render the animation
#
print(f"Starting render for job {job_id}")
print(f"Output path: {bpy.context.scene.render.filepath}")
print(f"Frame range: 1 to {bpy.context.scene.frame_end}")

try:
    bpy.ops.render.render(animation=True)
    print(f"Render completed successfully for job {job_id}")
    
    # Verify the output file was created
    output_path = bpy.context.scene.render.filepath
    if os.path.exists(output_path):
        file_size = os.path.getsize(output_path)
        print(f"Output file created: {output_path} (size: {file_size} bytes)")
    else:
        print(f"ERROR: Output file not found at {output_path}")
        sys.exit(1)
        
except Exception as e:
    print(f"ERROR during rendering: {str(e)}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
