import gi
import os
import numpy as np
import cv2
import hailo
from datetime import datetime
from hailo_platform import HailoRT

gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib

from hailo_apps_infra.hailo_rpi_common import (
    get_caps_from_pad,
    get_numpy_from_buffer,
    app_callback_class,
)
from hailo_apps_infra.detection_pipeline import GStreamerDetectionApp

# Set output directory for video recording
output_dir = "hailo_recordings"
os.makedirs(output_dir, exist_ok=True)

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
video_filename = os.path.join(output_dir, f"object_detection_{timestamp}.mp4")

# Load Hailo model
model_path = "your_model.hef"  # Replace with actual Hailo model
device = HailoRT.Device()
network_group = device.create_network_group(model_path)

# Define VideoWriter for recording
fourcc = cv2.VideoWriter_fourcc(*'mp4v')  
out = None  # Will be initialized in the callback

# -----------------------------------------------------------------------------------------------
# User-defined class to be used in the callback function
# -----------------------------------------------------------------------------------------------
class user_app_callback_class(app_callback_class):
    def __init__(self, width, height, fps):
        super().__init__()
        self.new_variable = 42  # Example variable
        self.frame_width = width
        self.frame_height = height
        self.fps = fps
        self.out = cv2.VideoWriter(video_filename, fourcc, fps, (width, height))

    def new_function(self):  # Example function
        return "The meaning of life is: "

# -----------------------------------------------------------------------------------------------
# User-defined callback function
# -----------------------------------------------------------------------------------------------

def process_frame(frame):
    """Runs inference on the frame and returns detection results"""
    input_tensor = np.expand_dims(frame, axis=0)
    output = network_group.infer(input_tensor)
    detections = []
    for obj in output:
        x, y, w, h, confidence, label = obj
        detections.append({
            "x": int(x), "y": int(y), "width": int(w), "height": int(h),
            "confidence": float(confidence), "label": str(label)
        })
    return detections

def app_callback(pad, info, user_data):
    buffer = info.get_buffer()
    if buffer is None:
        return Gst.PadProbeReturn.OK

    user_data.increment()
    frame_count = user_data.get_count()

    format, width, height = get_caps_from_pad(pad)
    frame = None
    if user_data.use_frame and format is not None and width is not None and height is not None:
        frame = get_numpy_from_buffer(buffer, format, width, height)

    # Run object detection
    detections = process_frame(frame) if frame is not None else []
    
    detection_count = 0
    for det in detections:
        x, y, w, h = det["x"], det["y"], det["width"], det["height"]
        label, conf = det["label"], det["confidence"]
        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
        cv2.putText(frame, f"{label}: {conf:.2f}", (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        detection_count += 1
    
    # Add detection count overlay
    cv2.putText(frame, f"Detections: {detection_count}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
    cv2.putText(frame, f"{user_data.new_function()} {user_data.new_variable}", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

    # Convert frame for display and saving
    frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
    user_data.set_frame(frame)

    # Write frame to MP4 video
    user_data.out.write(frame)
    
    print(f"Frame count: {frame_count}, Detections: {detection_count}")
    return Gst.PadProbeReturn.OK

if __name__ == "__main__":
    # Initialize GStreamer to determine video properties
    cap = cv2.VideoCapture(0)
    frame_width = int(cap.get(3))
    frame_height = int(cap.get(4))
    fps = int(cap.get(cv2.CAP_PROP_FPS)) if cap.get(cv2.CAP_PROP_FPS) > 0 else 30
    cap.release()

    # Create an instance of the user app callback class
    user_data = user_app_callback_class(frame_width, frame_height, fps)
    app = GStreamerDetectionApp(app_callback, user_data)
    app.run()

    # Release video writer
    user_data.out.release()
    print(f"Recording saved as: {video_filename}")

