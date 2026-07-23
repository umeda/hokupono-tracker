import numpy as np
import time
import sys

try:
    import sounddevice as sd
except (ImportError, OSError):
    print("Error: PortAudio library not found.")
    print("On Lubuntu/Ubuntu, you can fix this by running:")
    print("  sudo apt-get update && sudo apt-get install libportaudio2")
    sys.exit(1)

def run_diagnostic():
    print("=== AUDIO DIAGNOSTIC TOOL ===")
    
    # 1. System Bell
    print("\n1. Triggering System Bell (ASCII '\\a')...")
    sys.stdout.write('\a')
    sys.stdout.flush()
    time.sleep(1)

    # 2. Device List
    print("\n2. Detected Audio Devices:")
    devices = sd.query_devices()
    print(devices)
    print(f"\nDefault Output Device index: {sd.default.device[1]}")

    # Based on your list, your headset is index 6
    target_device = 6

    fs = 44100

    # 3. Standard Test Tone
    print(f"\n3. Playing 440Hz tone on Logitech Headset (Device {target_device})...")
    try:
        t = np.linspace(0, 0.5, int(fs * 0.5), False)
        # Simple sine wave at 440Hz (A4)
        wave = 0.2 * np.sin(2 * np.pi * 440 * t)
        sd.play(wave.astype(np.float32), fs, device=target_device)
        sd.wait()
    except Exception as e:
        print(f"Error playing standard tone: {e}")

    time.sleep(0.5)

    # 4. Trek Beep Tone
    print(f"4. Playing 1.5s Sonar-style 'Trek Ping' (2200Hz, Deeper Modulation) on device {target_device}...")
    try:
        duration, f = 1.5, 2200
        t = np.linspace(0, duration, int(fs * duration), False)
        # Constant carrier: 2200Hz sine
        carrier = np.sin(2 * np.pi * f * t)
        # Slower decay for the long "ping" effect with deeper 4Hz modulation
        envelope = np.exp(-3 * t) * (0.5 + 0.5 * np.cos(2 * np.pi * 4 * t))
        wave = 0.4 * carrier * envelope
        sd.play(wave.astype(np.float32), fs, device=target_device)
        sd.wait()
    except Exception as e:
        print(f"Error playing Trek tone: {e}")

    print("\nDiagnostic complete.")

if __name__ == "__main__":
    run_diagnostic()