import gi
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
from gpiozero import AngularServo

gi.require_version('Gtk', '3.0')
gi.require_version('Gst', '1.0')
from gi.repository import Gtk, Gst, GdkX11, GstVideo

# Inheritance from the app_callback_class
class user_app_callback_class(app_callback_class):
    def __init__(self):
        super().__init__()
        self.detection_counter = 0
        self.no_detection_counter = 0
        self.is_it_active = False
        self.servo = AngularServo(18, min_pulse_width=0.0006, max_pulse_width=0.0023)
        self.running = False  # Object detection starts OFF

def app_callback(pad, info, user_data):
    if not user_data.running:
        return Gst.PadProbeReturn.OK
    
    buffer = info.get_buffer()
    if buffer is None:
        return Gst.PadProbeReturn.OK
    
    user_data.increment()
    format, width, height = get_caps_from_pad(pad)
    frame = None
    if user_data.use_frame and format and width and height:
        frame = get_numpy_from_buffer(buffer, format, width, height)
    
    roi = hailo.get_roi_from_buffer(buffer)
    detections = roi.get_objects_typed(hailo.HAILO_DETECTION)
    object_detected = False
    
    for detection in detections:
        label = detection.get_label()
        confidence = detection.get_confidence()
        if confidence > 0.4 and label == "person":
            object_detected = True

    if object_detected:
        user_data.detection_counter += 1
        user_data.no_detection_counter = 0
        if user_data.detection_counter >= 4 and not user_data.is_it_active:
            user_data.servo.angle = 90
            user_data.is_it_active = True
            print("OBJECT DETECTED!")
    else:
        user_data.no_detection_counter += 1
        user_data.detection_counter = 0
        if user_data.no_detection_counter >= 5 and user_data.is_it_active:
            user_data.servo.angle = 0
            user_data.is_it_active = False
            print("Object Gone.")
    
    return Gst.PadProbeReturn.OK

class ObjectDetectionApp(Gtk.Window):
    def __init__(self):
        super().__init__(title="Object Detection GUI")
        self.set_default_size(800, 480)
        self.set_position(Gtk.WindowPosition.CENTER)
        
        self.user_data = user_app_callback_class()
        self.app = GStreamerDetectionApp(app_callback, self.user_data)
        
        self.box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.add(self.box)
        
        self.video_area = Gtk.DrawingArea()
        self.video_area.set_size_request(640, 480)
        self.video_area.connect("realize", self.on_realize)
        self.box.pack_start(self.video_area, True, True, 0)
        
        self.button_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.box.pack_start(self.button_box, False, False, 0)
        
        self.scan_button = Gtk.Button(label="Scan")
        self.scan_button.connect("clicked", self.start_detection)
        self.button_box.pack_start(self.scan_button, False, False, 0)
        
        self.stop_button = Gtk.Button(label="Stop")
        self.stop_button.connect("clicked", self.stop_detection)
        self.button_box.pack_start(self.stop_button, False, False, 0)
        
        self.save_button = Gtk.Button(label="Save")
        self.save_button.connect("clicked", self.save_frame)
        self.button_box.pack_start(self.save_button, False, False, 0)
        
        self.exit_button = Gtk.Button(label="Exit")
        self.exit_button.connect("clicked", self.exit_app)
        self.button_box.pack_start(self.exit_button, False, False, 0)
        
        self.show_all()
    
    def on_realize(self, widget):
        """Starts the camera stream using glimagesink for better Raspberry Pi support."""
        window = self.video_area.get_window()
        if not window:
            return
        
        xid = window.get_xid()
        
        self.pipeline = Gst.parse_launch(
            "v4l2src ! videoconvert ! videoscale ! video/x-raw,width=640,height=480 ! glimagesink"
        )

        # Ensure the sink integrates with GTK
        glimagesink = self.pipeline.get_by_name("glimagesink0")
        if glimagesink:
            glimagesink.set_window_handle(xid)

        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        self.pipeline.set_state(Gst.State.PLAYING)
    
    def start_detection(self, widget):
        self.user_data.running = True
        print("Object detection started.")
    
    def stop_detection(self, widget):
        self.user_data.running = False
        print("Object detection stopped.")
    
    def save_frame(self, widget):
        print("Frame saved.")
    
    def exit_app(self, widget):
        if hasattr(self, 'pipeline'):
            self.pipeline.set_state(Gst.State.NULL)
        Gtk.main_quit()
        os._exit(0)

if __name__ == "__main__":
    Gst.init(None)
    win = ObjectDetectionApp()
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()
