import sys
import numpy as np
import scipy.signal as signal
import sounddevice as sd
from rtlsdr import RtlSdr
from pynput import keyboard

# --- Configuration ---
SAMPLE_RATE = 256000     # 256 kHz (SDR rate)
AUDIO_RATE = 48000       # 48 kHz (Speaker rate)
DECIMATION = int(SAMPLE_RATE / AUDIO_RATE)
TUNE_STEP = 1000         # 1 kHz increments

class LiveSDR:
    def __init__(self, start_freq):
        self.sdr = RtlSdr()
        self.sdr.sample_rate = SAMPLE_RATE
        self.sdr.center_freq = start_freq
        self.sdr.gain = 'auto'
        self.current_freq = start_freq
        self.running = True

    def on_press(self, key):
        try:
            if key == keyboard.Key.up:
                self.current_freq += TUNE_STEP
                self.sdr.center_freq = self.current_freq
            elif key == keyboard.Key.down:
                self.current_freq -= TUNE_STEP
                self.sdr.center_freq = self.current_freq
            elif key == keyboard.Key.esc:
                self.running = False
            print(f"\rTuning: {self.current_freq/1e6:.4f} MHz", end="")
        except Exception as e:
            print(f"Error: {e}")

    def run(self):
        print(f"Listening on {self.current_freq/1e6} MHz. Use UP/DOWN to tune, ESC to quit.")
        
        # Start keyboard listener
        listener = keyboard.Listener(on_press=self.on_press)
        listener.start()

        # Audio Stream Setup
        # with sd.OutputStream(samplerate=AUDIO_RATE, channels=1) as stream:
        with sd.OutputStream(samplerate=AUDIO_RATE, channels=1, blocksize=2048) as stream:
            while self.running:
                # 1. Capture Raw IQ Samples
                samples = self.sdr.read_samples(16384 / 2) # Power of 2
                # samples = self.sdr.read_samples(65536)

                # 2. FM Demodulation (Polar Discriminator)
                # Angle of the product of current sample and conjugate of previous
                demodulated = np.angle(samples[1:] * np.conj(samples[:-1]))
                
                # 3. Resample to Audio Rate
                # Simple decimation for demo purposes
                audio_out = signal.decimate(demodulated, DECIMATION)
                
                # 4. Normalize and Play
                audio_out = audio_out / np.max(np.abs(audio_out))
                stream.write(audio_out.astype(np.float32))

        self.sdr.close()

if __name__ == "__main__":
    initial_freq = float(sys.argv[1]) if len(sys.argv) > 1 else 145600000
    radio = LiveSDR(initial_freq)
    radio.run()