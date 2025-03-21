import gi
import os
import numpy as np
import cv2
import hailo

gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib

from hailo_apps_infra.hailo_rpi_common import (
    get_caps_from_pad,
    get_numpy_from_buffer,
    app_callback_class,
)
from hailo_apps_infra.detection_pipeline import GStreamerDetectionApp

class user_app_callback_class(app_callback_class):
    def __init__(self):
        super().__init__()
        self.fps = 30  
        self.frame_size = (640, 480)  # Force to 640x640
        self.video_writer = None
        self.frame_count = 0

    def init_video_writer(self):
        if self.video_writer is None:
            print(f"[INFO] Initializing VideoWriter with size: {self.frame_size}")
            self.video_writer = cv2.VideoWriter(
                "output.mp4",
                cv2.VideoWriter_fourcc(*'mp4v'),
                self.fps,
                self.frame_size
            )

    def save_frame(self, frame):
        if self.video_writer is not None:
            print(f"[INFO] Saving frame {self.frame_count}")
            self.video_writer.write(frame)
            self.frame_count += 1
        else:
            print("[ERROR] VideoWriter not initialized!")

    def close_writer(self):
        if self.video_writer is not None:
            print(f"[INFO] Finished writing {self.frame_count} frames. Closing video.")
            self.video_writer.release()
            self.video_writer = None

def app_callback(pad, info, user_data):
    buffer = info.get_buffer()
    if buffer is None:
        print("[WARNING] Buffer is None.")
        return Gst.PadProbeReturn.OK

    user_data.increment()
    format, width, height = get_caps_from_pad(pad)

    if width is None or height is None:
        print("[ERROR] Invalid frame size.")
        return Gst.PadProbeReturn.OK

    if user_data.video_writer is None:
        user_data.init_video_writer()  # Ensure writer is initialized

    frame = get_numpy_from_buffer(buffer, format, width, height)
    if frame is None:
        print("[ERROR] Frame retrieval failed!")
        return Gst.PadProbeReturn.OK

    frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)  # Convert from RGB to BGR

    # Resize if needed
    if (width, height) != user_data.frame_size:
        frame = cv2.resize(frame, user_data.frame_size)

    user_data.save_frame(frame)

    return Gst.PadProbeReturn.OK

if __name__ == "__main__":
    user_data = user_app_callback_class()
    app = GStreamerDetectionApp(app_callback, user_data)
    app.run()
    user_data.close_writer()  # Ensure the file is properly saved
