import gi
import os
import numpy as np
import cv2
import hailo
from datetime import datetime
from gi.repository import Gst, GLib
from hailo_apps_infra.hailo_rpi_common import (
    get_caps_from_pad,
    get_numpy_from_buffer,
    app_callback_class,
)
from hailo_apps_infra.detection_pipeline import GStreamerDetectionApp

# -----------------------------------------------------------------------------------------------
# User-defined class to be used in the callback function
# -----------------------------------------------------------------------------------------------
class user_app_callback_class(app_callback_class):
    def __init__(self):
        super().__init__()
        self.new_variable = 42  # Example variable
    
    def new_function(self):  # Example function
        return "The meaning of life is: "

# -----------------------------------------------------------------------------------------------
# User-defined callback function
# -----------------------------------------------------------------------------------------------
timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")  # Timestamp up to hours

def app_callback(pad, info, user_data):
    frame_count = user_data.get_count()
    buffer = info.get_buffer()
    if buffer is None:
        return Gst.PadProbeReturn.OK

    success, map_info = buffer.map(Gst.MapFlags.READ)
    if not success:
        return Gst.PadProbeReturn.OK

    user_data.increment()
    string_to_print = f"Frame count: {user_data.get_count()}\n"
    format, width, height = get_caps_from_pad(pad)
    frame = None
    if user_data.use_frame and format and width and height:
        frame = get_numpy_from_buffer(buffer, format, min(width, 480), min(height, 480))
    
    roi = hailo.get_roi_from_buffer(buffer)
    detections = roi.get_objects_typed(hailo.HAILO_DETECTION)
    
    log_dir = "./log"
    os.makedirs(log_dir, exist_ok=True)
    log_file_path = os.path.join(log_dir, f"detections_log_{timestamp}.txt")
    
    detection_count = 0
    frame2 = np.frombuffer(map_info.data, dtype=np.uint8).reshape((height, width, 3))
    frame2 = np.array(frame2, copy=True)
    
    for detection in detections:
        label = detection.get_label()
        confidence = detection.get_confidence()
        bbox = detection.get_bbox()
        xmin, ymin, xmax, ymax = (
            int(bbox.xmin() * width), int(bbox.ymin() * height),
            int(bbox.xmax() * width), int(bbox.ymax() * height)
        )
        
        if label in ["Access Panel", "Bolt", "Cover Bolt", "Filter Mount Bolt", "Manifold Bolt", "Power Pack", "Rail Cover"]:
            roi.remove_object(detection)
            string_to_print += f"Frame: frame2_{frame_count:04d}.jpg -- Label: {label} -- Confidence: {confidence:.2f}\n"
            detection_count += 1
            
            with open(log_file_path, "a") as log_file:
                log_file.write(f"Frame: frame2_{frame_count:04d}.jpg -- Label: {label} -- Confidence: {confidence:.2f}\n")
            
            cv2.rectangle(frame2, (xmin, ymin), (xmax, ymax), (0, 255, 0), 2)
            cv2.putText(frame2, f"{label} {confidence:.2f}", (xmin, ymin-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
    
    frame2 = cv2.cvtColor(frame2, cv2.COLOR_RGB2BGR)
    output_path = f"captures/frame2_{frame_count:04d}.jpg"
    cv2.imwrite(output_path, frame2)
    
    if user_data.use_frame:
        cv2.putText(frame, f"Detections: {detection_count}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        cv2.putText(frame, f"{user_data.new_function()} {user_data.new_variable}", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        cv2.imwrite("home/fmonboard/Documents/frame.jpg", frame)
        user_data.set_frame(frame)
    
    print(string_to_print)
    return Gst.PadProbeReturn.OK

if __name__ == "__main__":
    user_data = user_app_callback_class()
    app = GStreamerDetectionApp(app_callback, user_data)
    app.run()
