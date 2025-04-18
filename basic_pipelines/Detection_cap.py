import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib
import os
import numpy as np
import cv2
import hailo

from hailo_apps_infra.hailo_rpi_common import (
    get_caps_from_pad,
    get_numpy_from_buffer,
    app_callback_class,
)
from hailo_apps_infra.detection_pipeline import GStreamerDetectionApp

# -----------------------------------------------------------------------------------------------
# User-defined class to be used in the callback function
# -----------------------------------------------------------------------------------------------
# Inheritance from the app_callback_class
class user_app_callback_class(app_callback_class):
    def __init__(self):
        super().__init__()
        self.new_variable = 42  # New variable example

    def new_function(self):  # New function example
        return "The meaning of life is: "

# -----------------------------------------------------------------------------------------------
# User-defined callback function
# -----------------------------------------------------------------------------------------------

# This is the callback function that will be called when data is available from the pipeline
def app_callback(pad, info, user_data):
    frame_count = user_data.get_count()
    # Get the GstBuffer from the probe info
    buffer = info.get_buffer()
    # Check if the buffer is valid
    if buffer is None:
        return Gst.PadProbeReturn.OK
    
    success, map_info = buffer.map(Gst.MapFlags.READ)
    if not success:
        return Gst.PadProbeReturn.OK


    # Using the user_data to count the number of frames
    user_data.increment()
    string_to_print = f"Frame count: {user_data.get_count()}\n"

    # Get the caps from the pad
    format, width, height = get_caps_from_pad(pad)
    print(width, height)
    # If the user_data.use_frame is set to True, we can get the video frame from the buffer
    
    
    frame = None
    if user_data.use_frame and format is not None and width is not None and height is not None:
        # Get video frame
        frame = get_numpy_from_buffer(buffer, format, width, height)
        print("writing frame")
        cv2.imwrite("home/fmonboard/Documents/frame.jpg", frame)

    # Get the detections from the buffer
    roi = hailo.get_roi_from_buffer(buffer)
    detections = roi.get_objects_typed(hailo.HAILO_DETECTION)

    # Parse the detections
    detection_count = 0
    for detection in detections:
        label = detection.get_label()
        bbox = detection.get_bbox()
        confidence = detection.get_confidence()
        if label == "person":
            # Get track ID
            track_id = 0
            track = detection.get_objects_typed(hailo.HAILO_UNIQUE_ID)
            if len(track) == 1:
                track_id = track[0].get_id()
            string_to_print += (f"Detection: ID: {track_id} Label: {label} Confidence: {confidence:.2f}\n")
            detection_count += 1
    #frame = get_numpy_from_buffer(buffer, format, width, height)
    #cv2.putText(frame, f"{user_data.new_function()} {user_data.new_variable}", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
    #cv2.putText(frame, f"{user_data.new_function()} {user_data.new_variable}", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
    #frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
    
    #output_path = f"captures/frame_{frame_count:04d}.jpg"
    #cv2.imwrite(output_path, frame)


    frame2 = np.frombuffer(map_info.data, dtype=np.uint8).reshape((height,width,3))
    for detection in hailo.get_roi_from_buffer(buffer).get_objects_typed(hailo.HAILO_DETECTION):
        #xmin, ymin, xmax, ymax = detection.get_bbox()
        
        bbox = detection.get_bbox()
        xmin = int(bbox.xmin() * width)
        ymin = int(bbox.ymin() * height)
        xmax = int(bbox.xmax() * width)
        ymax = int(bbox.ymax() * height)

        label = detection.get_label()
        confidence=detection.get_confidence()
        
        frame2 = np.array(frame2, copy=True)

        cv2.rectangle(frame2, (xmin,ymin), (xmax, ymax), color=(0,255,0), thickness=2)
        text = f"{label} {confidence:.2f}"
        cv2.putText(frame2, text, (xmin, ymin-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

    frame2 = cv2.cvtColor(frame2, cv2.COLOR_RGB2BGR)
    output_path = f"captures/frame2_{frame_count:04d}.jpg"
    cv2.imwrite(output_path, frame2)



    if user_data.use_frame:
        # Note: using imshow will not work here, as the callback function is not running in the main thread
        # Let's print the detection count to the frame
        cv2.putText(frame, f"Detections: {detection_count}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        # Example of how to use the new_variable and new_function from the user_data
        # Let's print the new_variable and the result of the new_function to the frame
        cv2.putText(frame, f"{user_data.new_function()} {user_data.new_variable}", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        # Convert the frame to BGR
        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        print(frame.dtype)
        cv2.imwrite("home/fmonboard/Documents/frame.jpg", frame)
        user_data.set_frame(frame)

    print(string_to_print)
    return Gst.PadProbeReturn.OK

if __name__ == "__main__":
    # Create an instance of the user app callback class
    user_data = user_app_callback_class()
    app = GStreamerDetectionApp(app_callback, user_data)
    app.run()
