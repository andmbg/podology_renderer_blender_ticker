import os
import sys
import bpy
import pickle

sys.path.insert(0, "/podology_renderer")

#
# File loading
#
canvas_path = "podology_renderer/render/canvas.blend"

# Process command line arguments (the pickle file path):
args = sys.argv

if "--" in args:
    args = args[args.index("--") + 1:]
else:
    raise ValueError("No arguments provided.")

if len(args) != 3:
    raise ValueError("Expected 3 arguments: ticker pickle path, job ID, frame step.")

ticker_path, job_id, frame_step = args
print("ticker path:" + ticker_path)
with open(ticker_path, "rb") as file:
    ticker = pickle.load(file)

print(ticker.to_dict())

#
# Render preparations
#

# Load the prepared .blend file
bpy.ops.wm.open_mainfile(filepath=canvas_path)

print(f"Opened canvas file: {canvas_path}")

# Verify/Set render output to video (if not already configured in the .blend file)
bpy.context.scene.render.engine = "BLENDER_EEVEE"
bpy.context.scene.render.filepath = f"podology_renderer/render/tmp/{job_id}.mp4"
bpy.context.scene.render.image_settings.file_format = "FFMPEG"
bpy.context.scene.render.ffmpeg.format = "MPEG4"  # H.264 MP4
bpy.data.scenes["Scene"].render.fps = ticker.fps
bpy.data.scenes["Scene"].frame_step = int(frame_step)

lane_spacing = 1.5
bpy.context.scene.frame_end = int(ticker.end * ticker.fps)

#
# Create text objects
#

# First, check existence of the shared material:
if "word_material" not in bpy.data.materials:
    raise ValueError("Material 'word_material' not found in the .blend file.")
else:
    mat = bpy.data.materials["word_material"]

# Create the objects:
for lane_idx, lane in enumerate(ticker.lanes):
    y_loc = lane_idx * lane_spacing
    
    for appearance in lane:

        # Create the text object
        bpy.ops.object.text_add(location=(0, y_loc, 0))
        text_obj = bpy.context.object
        text_obj.data.body = appearance.term

        text_obj.name = f"{appearance.apid}"
        text_obj["value"] = 0.0
    
        if text_obj.data.materials:
            text_obj.data.materials[0] = mat
        else:
            text_obj.data.materials.append(mat)

#
# Add a handler that updates the values of the text objects upon frame change;
# Also inserts keyframes at each frame, as this is necessary for headless rendering.
#
def update_values(scene):
    current_frame = scene.frame_current
    for obj in bpy.data.objects:
        if "value" in obj:
            t = current_frame / ticker.fps
            val = ticker.get_value(obj.name, t)  # You implement this
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
bpy.ops.render.render(animation=True)
