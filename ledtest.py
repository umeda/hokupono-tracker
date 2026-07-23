import serial
import serial.tools.list_ports
import time
import sys

# --- Configuration ---
BAUD_RATE = 115200
DELAY = 0.5  # 500 mS per state

def find_arduino_port():
    """Automatically detects the Arduino serial port."""
    ports = list(serial.tools.list_ports.comports())
    for p in ports:
        # Match based on description or common device patterns
        if "Arduino" in p.description or "ttyUSB" in p.device or "ttyACM" in p.device:
            return p.device
    return None

def main():
    port = find_arduino_port()
    if not port:
        print("Error: Could not find an Arduino or USB serial device.")
        sys.exit(1)

    try:
        ser = serial.Serial(port, BAUD_RATE, timeout=1)
        print(f"Connected to {port}. Waiting for Arduino reset...")
        
        # Standard delay for Arduino bootloader reset on serial connection
        time.sleep(2)
        ser.reset_input_buffer()

        # Cycle through all combinations twice
        for cycle in range(1, 3):
            print(f"\n--- Starting LED Color Cycle {cycle} ---")
            
            # Octal 0-7 represents: Black, Blue, Green, Cyan, Red, Magenta, Yellow, White
            for led1 in range(8):
                for led2 in range(8):
                    command = f"colr{led1},{led2}\n"
                    
                    print(f"Sending: {command.strip()}", end=" ", flush=True)
                    ser.write(command.encode())
                    
                    # Wait for ACK from Arduino
                    response = ser.readline().decode('utf-8').strip()
                    print(f"| Response: {response}")
                    
                    time.sleep(DELAY)

        # Set LEDs back to Black (Off) at the end
        ser.write(b"colr0,0\n")
        ser.close()
        print("\nTest complete. LEDs reset and port closed.")

    except Exception as e:
        print(f"\nError: {e}")

if __name__ == "__main__":
    main()