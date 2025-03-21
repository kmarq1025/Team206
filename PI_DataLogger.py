#!/usr/bin/env python3
import csv
import subprocess
import time
import datetime
import re
import os
from pathlib import Path

def run_pmic_command():
    """Run the vcgencmd pmic_read_adc command and return the output"""
    try:
        result = subprocess.run(['vcgencmd', 'pmic_read_adc'], 
                               capture_output=True, text=True, check=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error running vcgencmd: {e}")
        return None

def parse_pmic_output(output):
    """Parse the PMIC output and extract the values"""
    if not output:
        return {}
    
    # Regular expression to match key-value pairs like "3V7_WL_SW_A current(0)=0.05465208A"
    pattern = r'([^\s]+)\s+([^=]+)=([0-9.]+)([AV])'
    
    values = {}
    for line in output.strip().split('\n'):
        for match in re.finditer(pattern, line):
            name, type_id, value, unit = match.groups()
            # Create a column name: e.g., "3V7_WL_SW_A_current"
            column_name = f"{name}_{type_id.split('(')[0]}"
            values[column_name] = float(value)
    
    return values

def main():
    # Create output directory if it doesn't exist
    output_dir = Path("pmic_data")
    output_dir.mkdir(exist_ok=True)
    
    # Create filename with current date
    current_date = datetime.datetime.now().strftime("%Y-%m-%d")
    csv_file = output_dir / f"pmic_data_{current_date}.csv"
    
    # Check if the file exists to determine if we need to write headers
    file_exists = csv_file.exists()
    
    # Get initial PMIC reading to determine column headers
    initial_output = run_pmic_command()
    if not initial_output:
        print("Failed to get initial PMIC reading. Exiting.")
        return
    
    initial_values = parse_pmic_output(initial_output)
    
    # Define field names for CSV (timestamp + all PMIC values)
    fieldnames = ['timestamp'] + sorted(initial_values.keys())
    
    print(f"Writing PMIC data to {csv_file}")
    print(f"Sampling every 1 second. Press Ctrl+C to stop.")
    
    try:
        # Open and close the file with each write to ensure data is saved
        # even if power is suddenly lost
        while True:
            # Get current timestamp
            timestamp = datetime.datetime.now().isoformat()
            
            # Get PMIC reading
            output = run_pmic_command()
            if output:
                values = parse_pmic_output(output)
                
                # Add timestamp to values
                values['timestamp'] = timestamp
                
                # Open file, write data, and close immediately to ensure data is saved
                with open(csv_file, mode='a', newline='') as file:
                    writer = csv.DictWriter(file, fieldnames=fieldnames)
                    
                    # Write header only if the file is new or empty
                    if not file_exists or os.path.getsize(csv_file) == 0:
                        writer.writeheader()
                        file_exists = True
                    
                    # Write row to CSV
                    writer.writerow(values)
                    
                    # Flush and force write to disk
                    file.flush()
                    os.fsync(file.fileno())
                
                # Print status update
                print(f"Data recorded at {timestamp}", end='\r')
            else:
                print(f"Failed to get PMIC reading at {timestamp}")
            
            # Wait for 1 second
            time.sleep(1)
    
            # This code block is no longer used - moved to the main loop above
    
    except KeyboardInterrupt:
        print("\nStopping data collection.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()