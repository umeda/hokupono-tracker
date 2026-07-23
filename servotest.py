import serial
import serial.tools.list_ports
import time
import sys

# --- Configuration ---
BAUD_RATE = 115200
ELEVATION = 45
AZ_STEP = 10
DELAY = 1.0  # Seconds

def find_arduino_port():
    """Automatically detects the Arduino serial port."""
    ports = list(serial.tools.list_ports.comports())
    
    # 1. Try to find a port with "Arduino" in the description
    for p in ports:
        if "Arduino" in p.description:
            return p.device
            
    # 2. Fallback: Look for common USB-serial patterns if no "Arduino" string is found
    for p in ports:
        if "USB" in p.description or "ttyUSB" in p.device or "ttyACM" in p.device:
            return p.device
            
    return None

def run_test():
    port = find_arduino_port()
    if not port:
        print("Error: Could not find an Arduino or USB serial device.")
        sys.exit(1)

    try:
        ser = serial.Serial(port, BAUD_RATE, timeout=1)
        print(f"Connected to {port}. Waiting for Arduino reset...")
        
        ser.reset_input_buffer()
        time.sleep(2)  # Give Arduino time to reboot after serial connection

        for cycle in range(1, 3):
            print(f"\n--- Starting Azimuth Cycle {cycle} ---")
            
            for azimuth in range(0, 360, AZ_STEP):
                # Format: azelXXX,YY 
                # Using :03d and :02d ensures the string meets the >= 10 char requirement in main.cpp
                command = f"azel{azimuth:03d},{ELEVATION:02d}\n"
                
                print(f"Sending: {command.strip()}", end=" ", flush=True)
                ser.write(command.encode())
                
                # Wait for and print the ACK from Arduino
                response = ser.readline().decode('utf-8').strip()
                print(f"| Response: {response}")
                
                time.sleep(DELAY)

        # Return to home position (Azimuth 0, Elevation 0)
        print("\n--- Returning to Home Position (000,00) ---")
        home_command = "azel000,00\n"
        ser.write(home_command.encode())
        ser.readline()  # Wait for the final ACK
        time.sleep(DELAY)

        # Elevation Sweep: 0 to 180
        print("\n--- Starting Elevation Sweep (0 to 180) ---")
        for el in range(0, 181, 10):
            command = f"azel000,{el:02d}\n"
            print(f"Sending: {command.strip()}", end=" ", flush=True)
            ser.write(command.encode())
            response = ser.readline().decode('utf-8').strip()
            print(f"| Response: {response}")
            time.sleep(DELAY)

        # Elevation Sweep: 170 back to 0
        print("\n--- Starting Elevation Sweep (170 back to 0) ---")
        for el in range(170, -1, -10):
            command = f"azel000,{el:02d}\n"
            print(f"Sending: {command.strip()}", end=" ", flush=True)
            ser.write(command.encode())
            response = ser.readline().decode('utf-8').strip()
            print(f"| Response: {response}")
            time.sleep(DELAY)

        ser.close()
        print("\nTest complete. Port closed.")

    except Exception as e:
        print(f"\nError: {e}")

if __name__ == "__main__":
    run_test()