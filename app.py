import tkinter as tk
import subprocess
import time
import os
import threading
import datetime
import glob
import cv2
import numpy as np
from PIL import Image, ImageTk

# Create directories for saving data
RECORDINGS_DIR = "./data/recordings"
CAPTURES_DIR = "./data/captures"
os.makedirs(RECORDINGS_DIR, exist_ok=True)
os.makedirs(CAPTURES_DIR, exist_ok=True)

class RaspberryPiCameraApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Raspberry Pi Camera Control")
        
        # Get screen dimensions
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        
        # Application state
        self.detection_running = False
        self.recording = False
        self.detection_process = None
        self.selected_model = ""
        self.camera = None
        self.frame_thread = None
        self.running = False
        self.current_frame = None
        self.video_writer = None
        
        # Application layout - use two panels
        self.main_frame = tk.Frame(root)
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Left panel for video display
        self.video_frame = tk.Frame(self.main_frame, bg="black")
        self.video_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Video canvas
        self.canvas = tk.Canvas(self.video_frame, bg="black")
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # Right panel for controls
        self.control_panel = tk.Frame(self.main_frame, bg="#f0f0f0", width=300)
        self.control_panel.pack(side=tk.RIGHT, fill=tk.Y)
        self.control_panel.pack_propagate(False)  # Prevent shrinking
        
        # Scan available model files
        self.scan_model_files()
        
        # Create controls
        self.create_control_panel()
        
        # Start camera
        self.start_camera()
        
        # Start system monitoring
        self.start_system_monitoring()
        
        # Ensure cleanup on exit
        self.root.protocol("WM_DELETE_WINDOW", self.exit_application)
        
        # Create keyboard shortcuts
        self.root.bind("<q>", lambda e: self.exit_application())
        self.root.bind("<r>", lambda e: self.toggle_recording())
        self.root.bind("<c>", lambda e: self.capture_still())
    
    def scan_model_files(self):
        """Scan for available model files"""
        self.model_files = []
        
        # Get all .hef files in resources directory
        hef_files = glob.glob("./resources/*.hef")
        
        for file_path in hef_files:
            filename = os.path.basename(file_path)
            self.model_files.append((filename, file_path))
        
        # If no models found, add a placeholder
        if not self.model_files:
            self.model_files = [("No models found", "")]
        else:
            # Set default to first model
            self.selected_model = self.model_files[0][1]
    
    def create_control_panel(self):
        """Create control panel UI"""
        # Add padding
        control_inner = tk.Frame(self.control_panel, bg="#f0f0f0", padx=10, pady=10)
        control_inner.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = tk.Label(control_inner, text="Control Panel", 
                             font=("Arial", 16, "bold"), bg="#f0f0f0")
        title_label.pack(pady=10)
        
        # Start/Stop Button
        self.start_stop_btn = tk.Button(control_inner, text="Start Detection", 
                                     font=("Arial", 12), width=15, height=2,
                                     command=self.toggle_detection)
        self.start_stop_btn.pack(pady=10)
        
        # Record Button
        self.record_btn = tk.Button(control_inner, text="Record", 
                                 font=("Arial", 12), width=15, height=2,
                                 command=self.toggle_recording)
        self.record_btn.pack(pady=10)
        
        # Still Image Button
        self.still_btn = tk.Button(control_inner, text="Capture Still", 
                                font=("Arial", 12), width=15, height=2,
                                command=self.capture_still)
        self.still_btn.pack(pady=10)
        
        # Model Selection dropdown
        model_frame = tk.Frame(control_inner, bg="#f0f0f0")
        model_frame.pack(pady=10)
        
        model_label = tk.Label(model_frame, text="Model:", 
                             font=("Arial", 10), bg="#f0f0f0")
        model_label.pack(side=tk.LEFT, padx=5)
        
        # Create a StringVar and populate the dropdown
        self.model_var = tk.StringVar()
        model_names = [name for name, path in self.model_files]
        if model_names:
            self.model_var.set(model_names[0])
        
        model_menu = tk.OptionMenu(model_frame, self.model_var, *model_names, 
                                 command=self.on_model_selected)
        model_menu.config(width=15)
        model_menu.pack(side=tk.LEFT)
        
        # Exit Button
        self.exit_btn = tk.Button(control_inner, text="Exit", 
                               font=("Arial", 12), width=15, height=2,
                               command=self.exit_application)
        self.exit_btn.pack(pady=10)
        
        # Status indicators
        status_frame = tk.LabelFrame(control_inner, text="Status", 
                                   font=("Arial", 10, "bold"), bg="#f0f0f0")
        status_frame.pack(fill=tk.X, pady=10)
        
        self.temp_label = tk.Label(status_frame, text="CPU: -- °C", 
                                 font=("Arial", 10), bg="#f0f0f0", anchor="w")
        self.temp_label.pack(fill=tk.X, padx=5, pady=2)
        
        self.voltage_label = tk.Label(status_frame, text="Voltage: -- V", 
                                    font=("Arial", 10), bg="#f0f0f0", anchor="w")
        self.voltage_label.pack(fill=tk.X, padx=5, pady=2)
        
        self.status_label = tk.Label(status_frame, text="Status: Idle", 
                                   font=("Arial", 10), bg="#f0f0f0", anchor="w")
        self.status_label.pack(fill=tk.X, padx=5, pady=2)
        
        self.recording_label = tk.Label(status_frame, text="Recording: Off", 
                                      font=("Arial", 10), bg="#f0f0f0", anchor="w")
        self.recording_label.pack(fill=tk.X, padx=5, pady=2)
        
        # Help text
        help_frame = tk.LabelFrame(control_inner, text="Keyboard Shortcuts", 
                                 font=("Arial", 10, "bold"), bg="#f0f0f0")
        help_frame.pack(fill=tk.X, pady=10)
        
        shortcuts = [
            "Q: Quit application",
            "R: Start/stop recording",
            "C: Capture still image"
        ]
        
        for shortcut in shortcuts:
            tk.Label(help_frame, text=shortcut, font=("Arial", 9), 
                   bg="#f0f0f0", anchor="w").pack(fill=tk.X, padx=5, pady=1)
    
    def on_model_selected(self, selection):
        """Handle model selection from dropdown"""
        for name, path in self.model_files:
            if name == selection:
                self.selected_model = path
                break
    
    def start_camera(self):
        """Start the camera using OpenCV"""
        if hasattr(self, 'camera') and self.camera is not None and self.camera.isOpened():
            # Camera is already running
            return True
        
        # Try to open the camera - this will use the default device
        self.camera = cv2.VideoCapture(0)
        
        # Set camera properties
        self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        
        if not self.camera.isOpened():
            self.status_label.config(text="Status: Failed to open camera")
            return False
        
        self.status_label.config(text="Status: Camera started")
        
        # Start the frame update thread
        self.running = True
        self.frame_thread = threading.Thread(target=self.update_frames)
        self.frame_thread.daemon = True
        self.frame_thread.start()
        
        return True
    
    def update_frames(self):
        """Update frames from camera"""
        try:
            while self.running and self.camera is not None and self.camera.isOpened():
                # Read a frame
                ret, frame = self.camera.read()
                
                if ret:
                    # Store current frame
                    self.current_frame = frame.copy()
                    
                    # Create a copy for display
                    display_frame = frame.copy()
                    
                    # Add status text
                    text = "Recording" if self.recording else "Ready"
                    cv2.putText(display_frame, text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 
                              0.7, (0, 255, 0), 2)
                    
                    # Add recording indicator
                    if self.recording:
                        cv2.putText(display_frame, "REC ●", (display_frame.shape[1] - 100, 30), 
                                  cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                    
                    # Convert to RGB for tkinter
                    rgb_frame = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
                    
                    # Convert to PIL Image
                    pil_img = Image.fromarray(rgb_frame)
                    
                    # Resize to fit canvas while maintaining aspect ratio
                    canvas_width = self.canvas.winfo_width()
                    canvas_height = self.canvas.winfo_height()
                    
                    if canvas_width > 1 and canvas_height > 1:
                        # Calculate ratios
                        img_ratio = rgb_frame.shape[1] / rgb_frame.shape[0]
                        canvas_ratio = canvas_width / canvas_height
                        
                        if img_ratio > canvas_ratio:
                            # Width constrained
                            new_width = canvas_width
                            new_height = int(canvas_width / img_ratio)
                        else:
                            # Height constrained
                            new_height = canvas_height
                            new_width = int(canvas_height * img_ratio)
                        
                        pil_img = pil_img.resize((new_width, new_height), Image.NEAREST)
                    
                    # Convert to tkinter PhotoImage
                    self.photo = ImageTk.PhotoImage(image=pil_img)
                    
                    # Update canvas
                    self.canvas.config(width=canvas_width, height=canvas_height)
                    self.canvas.create_image(canvas_width//2, canvas_height//2, image=self.photo, anchor=tk.CENTER)
                    
                    # Handle recording
                    if self.recording and self.video_writer is not None:
                        self.video_writer.write(frame)
                
                # Maintain a stable frame rate
                time.sleep(0.03)  # ~30 FPS
                
        except Exception as e:
            print(f"Error in frame update: {e}")
        
        # Clean up
        self.release_camera()
    
    def release_camera(self):
        """Release the camera cleanly"""
        if hasattr(self, 'camera') and self.camera is not None:
            self.camera.release()
            self.camera = None
    
    def stop_camera(self):
        """Stop the camera and frame updates"""
        self.running = False
        
        # Wait for the frame thread to finish
        if self.frame_thread is not None:
            self.frame_thread.join(timeout=1.0)
            self.frame_thread = None
        
        # Release the camera
        self.release_camera()
        
        # Clear the canvas
        self.canvas.delete("all")
    
    def start_system_monitoring(self):
        """Monitor system stats"""
        def update_stats():
            while True:
                try:
                    # Get CPU temperature
                    with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                        temp = float(f.read()) / 1000.0
                    self.temp_label.config(text=f"CPU: {temp:.1f} °C")
                    
                    # Get system voltage (requires vcgencmd)
                    try:
                        voltage_output = subprocess.check_output(['vcgencmd', 'measure_volts', 'core'], 
                                                              universal_newlines=True)
                        voltage = float(voltage_output.replace('volt=', '').replace('V', ''))
                        self.voltage_label.config(text=f"Voltage: {voltage:.1f} V")
                    except:
                        self.voltage_label.config(text="Voltage: N/A")
                    
                except Exception as e:
                    print(f"Error updating stats: {e}")
                
                time.sleep(1)
        
        # Start monitoring thread
        monitor_thread = threading.Thread(target=update_stats)
        monitor_thread.daemon = True
        monitor_thread.start()
    
    def toggle_detection(self):
        """Toggle object detection on/off"""
        if not self.detection_running:
            # Update UI
            self.start_stop_btn.config(text="Stop Detection")
            self.status_label.config(text="Status: Starting detection...")
            
            # Stop the camera
            self.stop_camera()
            
            # Make sure detection data directories exist
            os.makedirs(RECORDINGS_DIR, exist_ok=True)
            os.makedirs(CAPTURES_DIR, exist_ok=True)
            
            # Create flag files with default values
            record_flag_path = "record_flag.txt"
            capture_flag_path = "capture_flag.txt"
            
            # Initialize flag files
            with open(record_flag_path, "w") as f:
                f.write("0")
            with open(capture_flag_path, "w") as f:
                f.write("")
                
            print(f"Created flag files: {record_flag_path}, {capture_flag_path}")
            
            # Start the detection process
            try:
                cmd = [
                    "python", 
                    "./basic_pipelines/detection.py", 
                    "--input", "rpi", 
                    "--hef", self.selected_model
                ]
                
                # Print the command
                cmd_str = " ".join(cmd)
                print(f"Executing: {cmd_str}")
                
                # Wait a moment to ensure camera is released
                time.sleep(1)
                
                # Start the detection process
                self.detection_process = subprocess.Popen(cmd)
                
                # Check if process started successfully
                if self.detection_process.poll() is None:
                    self.detection_running = True
                    self.status_label.config(text="Status: Detection running")
                else:
                    self.status_label.config(text="Status: Process failed to start")
                    # Restart camera
                    self.start_camera()
            except Exception as e:
                self.status_label.config(text=f"Status: Error: {str(e)}")
                # Restart camera
                self.start_camera()
        else:
            # Stop detection process
            if self.detection_process is not None:
                try:
                    self.detection_process.terminate()
                    # Wait for process to terminate
                    timeout = 5
                    for _ in range(timeout * 10):
                        if self.detection_process.poll() is not None:
                            break
                        time.sleep(0.1)
                    
                    # If still running, kill it
                    if self.detection_process.poll() is None:
                        self.detection_process.kill()
                        time.sleep(0.5)
                    
                    self.detection_process = None
                except Exception as e:
                    print(f"Error terminating detection process: {str(e)}")
            
            # Update UI
            self.start_stop_btn.config(text="Start Detection")
            self.detection_running = False
            self.status_label.config(text="Status: Detection stopped")
            
            # Restart camera
            self.start_camera()
    
    def toggle_recording(self):
        """Toggle video recording"""
        if not self.recording:
            # Start recording
            if not self.detection_running:
                # Make sure we have a camera and a frame
                if self.camera is None or not hasattr(self, 'current_frame') or self.current_frame is None:
                    self.status_label.config(text="Status: Camera not ready")
                    return
                
                # Get timestamp for filename
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                output_file = os.path.join(RECORDINGS_DIR, f"recording_{timestamp}.avi")
                
                print(f"Starting recording to: {output_file}")
                
                try:
                    # Get frame dimensions
                    height, width = self.current_frame.shape[:2]
                    
                    # Create video writer
                    fourcc = cv2.VideoWriter_fourcc(*'XVID')
                    self.video_writer = cv2.VideoWriter(output_file, fourcc, 20.0, (width, height))
                    
                    if not self.video_writer.isOpened():
                        print("Failed to open video writer")
                        self.status_label.config(text="Status: Failed to start recording")
                        return
                    
                    self.recording = True
                    self.record_btn.config(text="Stop Recording", bg="#ff7777")
                    self.recording_label.config(text="Recording: On")
                    
                    # Start a thread to update the timer
                    def update_timer():
                        start_time = time.time()
                        while self.recording:
                            elapsed = int(time.time() - start_time)
                            self.recording_label.config(text=f"Recording: {elapsed}s")
                            time.sleep(1)
                    
                    timer_thread = threading.Thread(target=update_timer)
                    timer_thread.daemon = True
                    timer_thread.start()
                    
                except Exception as e:
                    print(f"Error starting recording: {str(e)}")
                    self.status_label.config(text=f"Status: Recording error")
                    return
            else:
                # Signal detection process to start recording
                record_flag_path = "record_flag.txt"
                with open(record_flag_path, "w") as f:
                    f.write("1")
                self.recording = True
                self.record_btn.config(text="Stop Recording", bg="#ff7777")
                self.recording_label.config(text="Recording: On")
                print(f"Recording signal sent via {record_flag_path}")
        else:
            # Stop recording
            if not self.detection_running:
                if self.video_writer is not None:
                    self.video_writer.release()
                    self.video_writer = None
            else:
                # Signal detection process to stop recording
                record_flag_path = "record_flag.txt"
                with open(record_flag_path, "w") as f:
                    f.write("0")
                print(f"Stop recording signal sent via {record_flag_path}")
            
            self.recording = False
            self.record_btn.config(text="Record", bg="#f0f0f0")
            self.recording_label.config(text="Recording: Off")
    
    def capture_still(self):
        """Capture a still image"""
        if not self.detection_running:
            # Make sure we have a camera and a frame
            if self.camera is None or not hasattr(self, 'current_frame') or self.current_frame is None:
                self.status_label.config(text="Status: Camera not ready")
                return
            
            # Get timestamp for filename
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = os.path.join(CAPTURES_DIR, f"capture_{timestamp}.jpg")
            
            # Save the image
            success = cv2.imwrite(output_file, self.current_frame)
            
            if success:
                print(f"Captured image saved to: {output_file}")
                self.status_label.config(text=f"Status: Captured to {os.path.basename(output_file)}")
            else:
                print("Failed to save image")
                self.status_label.config(text="Status: Failed to save image")
        else:
            # Signal detection process
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            capture_flag_path = "capture_flag.txt"
            with open(capture_flag_path, "w") as f:
                f.write(timestamp)
            self.status_label.config(text="Status: Capture signal sent")
            print(f"Capture signal sent via {capture_flag_path}")
    
    def exit_application(self):
        """Exit the application cleanly"""
        print("Shutting down application...")
        
        # Stop recording if active
        if self.recording:
            self.toggle_recording()
        
        # Stop camera
        self.stop_camera()
        
        # Stop detection process if running
        if self.detection_running and self.detection_process is not None:
            try:
                self.detection_process.terminate()
                time.sleep(0.5)
                if self.detection_process.poll() is None:
                    self.detection_process.kill()
            except:
                pass
        
        # Exit
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    # Set window size and position
    root.geometry("1024x768")
    app = RaspberryPiCameraApp(root)
    root.mainloop()
