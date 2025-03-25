import tkinter as tk
import subprocess
import time
import os
import threading
import datetime
import glob
import cv2
from picamera2 import Picamera2

# Create directories for saving data
RECORDINGS_DIR = "./data/recordings"
CAPTURES_DIR = "./data/captures"
os.makedirs(RECORDINGS_DIR, exist_ok=True)
os.makedirs(CAPTURES_DIR, exist_ok=True)

class CameraThread(threading.Thread):
    """Thread class for camera operations"""
    def __init__(self):
        super().__init__()
        self.daemon = True
        self.running = False
        self.recording = False
        self.video_writer = None
        self.current_frame = None
        
    def run(self):
        """Main thread function"""
        print("Starting camera thread...")
        
        # Initialize PiCamera2
        picam2 = None
        try:
            picam2 = Picamera2()
            
            # Configure camera for preview with a common format
            config = picam2.create_preview_configuration(
                main={"size": (640, 480), "format": "RGB888"}
            )
            picam2.configure(config)
            
            # Print camera config for debugging
            print(f"Camera configuration: {config}")
            
            # Start camera
            picam2.start()
            print("Camera started")
            
            # Give camera time to initialize
            time.sleep(2)
            
            # Create window - use the exact same window setup as the test script
            window_name = "Raspberry Pi Camera"
            cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
            
            print("Press 'q' to quit")
            
            self.running = True
            
            # Main loop
            while self.running:
                # Capture frame
                frame = picam2.capture_array()
                
                if frame is not None:
                    # Store current frame for other operations
                    self.current_frame = frame.copy()
                    
                    # Convert from RGB to BGR (OpenCV uses BGR)
                    frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                    
                    # Display the frame
                    cv2.imshow(window_name, frame_bgr)
                    
                    # Handle recording if active
                    if self.recording and self.video_writer is not None:
                        self.video_writer.write(frame_bgr)
                else:
                    print("Received empty frame")
                
                # Check for key press (wait 1ms)
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    break
                elif key == ord('r'):  # Toggle recording
                    if not self.recording:
                        self.start_recording()
                    else:
                        self.stop_recording()
                elif key == ord('c'):  # Capture still
                    self.capture_still()
            
        except Exception as e:
            print(f"Camera thread error: {str(e)}")
        
        finally:
            # Clean up
            self.running = False
            if self.recording:
                self.stop_recording()
                
            if picam2 is not None:
                picam2.close()
            cv2.destroyAllWindows()
            print("Camera thread finished")
    
    def start_recording(self):
        """Start video recording"""
        if self.recording:
            return
            
        # Get timestamp for filename
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = os.path.join(RECORDINGS_DIR, f"recording_{timestamp}.avi")
        
        print(f"Starting recording to: {output_file}")
        
        try:
            # Get frame dimensions from current frame
            if self.current_frame is not None:
                height, width = self.current_frame.shape[:2]
            else:
                # Default dimensions
                width, height = 640, 480
            
            # Create video writer
            fourcc = cv2.VideoWriter_fourcc(*'XVID')
            self.video_writer = cv2.VideoWriter(output_file, fourcc, 20.0, (width, height))
            
            if not self.video_writer.isOpened():
                print("Failed to open video writer")
                return
            
            self.recording = True
            print(f"Recording started to {output_file}")
            
        except Exception as e:
            print(f"Error starting recording: {str(e)}")
            if self.video_writer is not None:
                self.video_writer.release()
                self.video_writer = None
    
    def stop_recording(self):
        """Stop the current recording"""
        if not self.recording:
            return
            
        self.recording = False
        
        if self.video_writer is not None:
            self.video_writer.release()
            self.video_writer = None
            
        print("Recording stopped")
    
    def capture_still(self):
        """Capture a still image"""
        try:
            if self.current_frame is None:
                print("No frame available")
                return None
                
            # Get timestamp for filename
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = os.path.join(CAPTURES_DIR, f"capture_{timestamp}.jpg")
            
            # Convert RGB to BGR for OpenCV
            frame_bgr = cv2.cvtColor(self.current_frame, cv2.COLOR_RGB2BGR)
            success = cv2.imwrite(output_file, frame_bgr)
            
            if success:
                print(f"Captured image saved to: {output_file}")
                return output_file
            else:
                print("Failed to save image")
                return None
                
        except Exception as e:
            print(f"Error capturing image: {str(e)}")
            return None
    
    def stop(self):
        """Stop the camera thread"""
        self.running = False


class RaspberryPiApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Raspberry Pi Camera Control")
        
        # Get screen dimensions
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        
        # Set control window position (right side of screen)
        control_width = 300
        control_x = screen_width - control_width
        
        self.root.geometry(f"{control_width}x{screen_height}+{control_x}+0")
        
        # Application state
        self.recording = False
        self.camera_thread = None
        
        # Create control panel
        self.control_panel = tk.Frame(self.root, bg="#f0f0f0", padx=10, pady=10)
        self.control_panel.pack(fill=tk.BOTH, expand=True)
        
        # Create control buttons
        self.create_control_panel()
        
        # Start camera in a separate thread
        self.start_camera()
    
    def create_control_panel(self):
        """Create control panel UI"""
        # Title
        title_label = tk.Label(self.control_panel, text="Camera Control", 
                             font=("Arial", 16, "bold"), bg="#f0f0f0")
        title_label.pack(pady=20)
        
        # Record Button
        self.record_btn = tk.Button(self.control_panel, text="Record", 
                                 font=("Arial", 12), width=15, height=2,
                                 command=self.toggle_recording)
        self.record_btn.pack(pady=10)
        
        # Still Image Button
        self.still_btn = tk.Button(self.control_panel, text="Capture Still", 
                                font=("Arial", 12), width=15, height=2,
                                command=self.capture_still)
        self.still_btn.pack(pady=10)
        
        # Status indicators
        status_frame = tk.LabelFrame(self.control_panel, text="Status", 
                                   font=("Arial", 10, "bold"), bg="#f0f0f0")
        status_frame.pack(fill=tk.X, padx=5, pady=10)
        
        self.status_label = tk.Label(status_frame, text="Status: Starting...", 
                                   font=("Arial", 10), bg="#f0f0f0", anchor="w")
        self.status_label.pack(fill=tk.X, padx=5, pady=2)
        
        self.recording_label = tk.Label(status_frame, text="Recording: Off", 
                                      font=("Arial", 10), bg="#f0f0f0", anchor="w")
        self.recording_label.pack(fill=tk.X, padx=5, pady=2)
        
        # Help text
        help_frame = tk.LabelFrame(self.control_panel, text="Keyboard Shortcuts", 
                                 font=("Arial", 10, "bold"), bg="#f0f0f0")
        help_frame.pack(fill=tk.X, padx=5, pady=10)
        
        shortcuts = [
            "Q: Quit camera view",
            "R: Start/stop recording",
            "C: Capture still image"
        ]
        
        for shortcut in shortcuts:
            tk.Label(help_frame, text=shortcut, font=("Arial", 9), 
                   bg="#f0f0f0", anchor="w").pack(fill=tk.X, padx=5, pady=1)
        
        # Exit Button
        self.exit_btn = tk.Button(self.control_panel, text="Exit", 
                               font=("Arial", 12), width=15, height=2,
                               command=self.exit_application)
        self.exit_btn.pack(pady=20)
    
    def start_camera(self):
        """Start the camera thread"""
        self.camera_thread = CameraThread()
        self.camera_thread.start()
        self.status_label.config(text="Status: Camera starting...")
        
        # Start monitoring thread to update UI based on camera state
        self.start_monitoring()
    
    def start_monitoring(self):
        """Monitor camera thread status to update UI"""
        def monitor_camera():
            while True:
                if self.camera_thread is not None:
                    # Update recording status
                    recording_status = self.camera_thread.recording
                    if recording_status != self.recording:
                        self.recording = recording_status
                        self.recording_label.config(text=f"Recording: {'On' if recording_status else 'Off'}")
                        self.record_btn.config(
                            text="Stop Recording" if recording_status else "Record",
                            bg="#ff7777" if recording_status else "#f0f0f0"
                        )
                    
                    # Update running status
                    if self.camera_thread.running:
                        if self.status_label.cget("text") == "Status: Camera starting...":
                            self.status_label.config(text="Status: Camera running")
                    else:
                        self.status_label.config(text="Status: Camera stopped")
                        break
                
                time.sleep(0.5)
        
        monitor_thread = threading.Thread(target=monitor_camera)
        monitor_thread.daemon = True
        monitor_thread.start()
    
    def toggle_recording(self):
        """Toggle recording on/off"""
        if self.camera_thread is not None:
            if not self.camera_thread.recording:
                self.camera_thread.start_recording()
            else:
                self.camera_thread.stop_recording()
    
    def capture_still(self):
        """Capture a still image"""
        if self.camera_thread is not None:
            self.camera_thread.capture_still()
    
    def exit_application(self):
        """Exit the application cleanly"""
        if self.camera_thread is not None:
            self.camera_thread.stop()
        
        # Exit
        self.root.quit()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = RaspberryPiApp(root)
    root.mainloop()
