import curses
import argparse
import os
import time
import numpy as np
import tomllib
import sys
import urllib.parse
from skyfield.api import Topos, load
from datetime import datetime, timedelta

try:
    import sounddevice as sd
    # Querying devices once at startup confirms the PortAudio backend is functional
    sd.query_devices()
    HAS_SOUND = True
except (ImportError, Exception):
    HAS_SOUND = False

def find_best_output_device():
    """Finds Logitech specifically, or falls back to generic USB/Headset devices."""
    if not HAS_SOUND: return None
    try:
        devices = sd.query_devices()
        # Priority 1: Specifically look for the known Logitech device
        for i, dev in enumerate(devices):
            if 'Logitech' in dev['name'] and dev['max_output_channels'] > 0:
                return i
        # Priority 2: Look for any USB or Headset device
        for i, dev in enumerate(devices):
            if any(kw in dev['name'] for kw in ['USB', 'Headset']) and dev['max_output_channels'] > 0:
                return i
    except: pass
    return None # Falls back to sd.default.device[1]

def play_trek_beep():
    """Plays a short electronic chirp reminiscent of TOS bridge consoles."""
    if not HAS_SOUND:
        return
    try:
        dev = find_best_output_device()
        # If we didn't find a preferred device and there is no default device, stop here
        if dev is None and sd.default.device[1] == -1:
            return

        fs, duration, f = 44100, 1.5, 2200
        t = np.linspace(0, duration, int(fs * duration), False)
        # Constant carrier: 2200Hz sine
        carrier = np.sin(2 * np.pi * f * t)
        # Slow exponential decay (-3) for a 1.5s sonar-style tail
        # Deeper 4Hz cosine modulation for a more pronounced thrumming effect
        # (0.5 + 0.5 * cos) makes the modulation vary from 0 to 1
        envelope = np.exp(-3 * t) * (0.5 + 0.5 * np.cos(2 * np.pi * 4 * t))
        wave = 0.2 * carrier * envelope
        sd.play(wave.astype(np.float32), fs, device=dev)
    except Exception:
        pass

def get_next_pass(iss, observer, ts):
    """Finds the start time of the very next pass."""
    t0 = ts.now()
    # Corrected: Use .tt_jd to create a time 1 day (1.0) in the future
    t1 = ts.tt_jd(t0.tt + 1.0) 
    
    times, events = iss.find_events(observer, t0, t1, altitude_degrees=0)
    
    for t, event in zip(times, events):
        if event == 0:  # Event 0 is 'rise above horizon' (AOS)
            return t
    return None

def get_data(iss, observer, ts, config):
    BASE_FREQ_MHZ = config['base_frequency_mhz']
    C_MS = config['c_ms']
    step_khz = config['tuning_increment']

    t = ts.now()
    difference = iss - observer
    topocentric = difference.at(t)
    alt, az, distance = topocentric.altaz()
    
    # Doppler Calculation
    v_vector = topocentric.velocity.km_per_s
    p_vector = topocentric.position.km / distance.km
    range_rate_km_s = np.dot(v_vector, p_vector)
    range_rate_m_s = range_rate_km_s * 1000.0
    
    doppler_freq_mhz = BASE_FREQ_MHZ * (1 - (range_rate_m_s / C_MS))
    shift_khz = (doppler_freq_mhz - BASE_FREQ_MHZ) * 1000
    
    rounded_shift_khz = round(shift_khz / step_khz) * step_khz
    tuned_freq_mhz = BASE_FREQ_MHZ + (rounded_shift_khz / 1000.0)
    
    return {
        "time": datetime.now(),
        "alt": alt.degrees,
        "az": az.degrees,
        "shift_raw": shift_khz,
        "tuned_freq": tuned_freq_mhz
    }

def run_curses(stdscr, iss, observer, ts, config, sound_mode):
    curses.curs_set(0)
    # Initialize color pairs
    if curses.has_colors():
        curses.start_color()
        curses.init_pair(1, curses.COLOR_YELLOW, curses.COLOR_BLACK)

    stdscr.nodelay(True)
    stdscr.timeout(1000)

    next_aos_t = None
    last_aos_check = datetime.min
    step_khz = config['tuning_increment']
    sat_name = iss.name
    last_freq = None

    while True:
        stdscr.clear()
        data = get_data(iss, observer, ts, config)

        if last_freq is not None and data['tuned_freq'] != last_freq:
            if sound_mode == "trek":
                play_trek_beep()
            elif sound_mode == "system":
                curses.beep()
        last_freq = data['tuned_freq']
        
        stdscr.addstr(1, 2, f"--- {sat_name} LIVE TRACKER ({step_khz}kHz Steps) ---", curses.A_BOLD)
        stdscr.addstr(3, 4, f"Local Time:     {data['time'].strftime('%H:%M:%S')}")
        stdscr.addstr(4, 4, f"Elevation:      {data['alt']:.2f}°")
        stdscr.addstr(5, 4, f"Azimuth:        {data['az']:.2f}°")
        
        doppler_str = f"Doppler Shift:  {data['shift_raw']:+.3f} kHz "
        tune_str = f"(tune {data['tuned_freq']:.3f} MHz)"
        stdscr.addstr(7, 4, doppler_str + tune_str, curses.color_pair(1) if data['alt'] > 0 else curses.A_NORMAL)
        
        if data['alt'] > 0:
            stdscr.addstr(9, 4, "STATUS: IN PASS (SIGNAL ACTIVE)", curses.A_REVERSE)
            next_aos_t = None 
        else:
            stdscr.addstr(9, 4, "STATUS: BELOW HORIZON")
            
            # Use 'is None' check to avoid the TypeError
            if next_aos_t is None or (datetime.now() - last_aos_check).total_seconds() > 60:
                next_aos_t = get_next_pass(iss, observer, ts)
                last_aos_check = datetime.now()
            
            # Change this line here:
            if next_aos_t is not None:
                # Calculate time remaining
                diff_seconds = int((next_aos_t - ts.now()) * 86400)
                
                if diff_seconds > 0:
                    hours, remainder = divmod(diff_seconds, 3600)
                    minutes, seconds = divmod(remainder, 60)
                    stdscr.addstr(10, 4, f"Next AOS in:    {hours:02d}:{minutes:02d}:{seconds:02d}", curses.A_BOLD)
                else:
                    # If time is in the past, reset to find the next one
                    next_aos_t = None


        stdscr.addstr(12, 2, "Press 'q' to quit")
        stdscr.refresh()
        if stdscr.getch() == ord('q'): break

def main():
    # Load configuration relative to script location
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, 'tracker.toml')
    
    with open(config_path, 'rb') as f:
        config = tomllib.load(f)

    parser = argparse.ArgumentParser()
    parser.add_argument("-satindex", type=int)
    parser.add_argument("-sound", choices=["system", "trek"], help="Notification sound type (default: silence)")
    args = parser.parse_args()

    # Satellite Selection Logic
    sat_list = config['satellites']
    if args.satindex is not None:
        sel_idx = args.satindex - 1
    else:
        print("Available satellites (from tracker.toml):")
        for i, entry in enumerate(sat_list, 1):
            print(f"{i}: {entry['name']} (NORAD {entry['norad_id']}) - {entry['frequency']:.3f} MHz")
        try:
            val = input(f"\nSelect a satellite (1-{len(sat_list)}): ")
            sel_idx = int(val) - 1
        except (ValueError, EOFError, KeyboardInterrupt):
            return

    if not (0 <= sel_idx < len(sat_list)):
        print("Error: Invalid satellite index.")
        return

    selected_entry = sat_list[sel_idx]
    selected_name = selected_entry['name']
    selected_id = selected_entry['norad_id']
    
    # Override global base frequency with the satellite-specific frequency
    config['base_frequency_mhz'] = selected_entry['frequency']
    
    satellites = []
    max_retries = 3
    for attempt in range(max_retries):
        try:
            # Build search URL using CelesTrak GP API to find the satellite by NORAD ID
            query_params = urllib.parse.urlencode({'CATNR': selected_id, 'FORMAT': 'TLE'})
            search_url = f"{config['tle_url']}?{query_params}"

            # Skyfield caches by filename. Since the GP API filename is always 'gp.php',
            # we force a reload to ensure the specific search query is executed 
            # instead of loading the cached result from the first run.
            satellites = load.tle_file(search_url, reload=True)
            break # If successful, break the retry loop
        except Exception as e:
            error_message = str(e)
            is_404 = "404" in error_message and "Not Found" in error_message

            if is_404:
                print(f"\nAttempt {attempt + 1}/{max_retries}: Received 404 Not Found for NORAD ID {selected_id} ({selected_name}).")
            else:
                print(f"\nAttempt {attempt + 1}/{max_retries}: Error retrieving TLE for NORAD ID {selected_id} ({selected_name}).")
            print(f"Details: {error_message}")

            if attempt < max_retries - 1:
                sleep_time = 2 ** attempt # Exponential backoff: 1, 2, 4 seconds
                print(f"Retrying in {sleep_time} seconds...")
                time.sleep(sleep_time)
            else:
                print(f"Max retries reached. Could not retrieve TLE for NORAD ID {selected_id} ({selected_name}).")
                return # Exit main if all retries failed

    # Find the exact match in the search results
    selected_sat = next((s for s in satellites if s.model.satnum == selected_id), None)
    if not selected_sat and satellites:
        selected_sat = satellites[0]

    if not selected_sat:
        print(f"Error: Satellite NORAD ID {selected_id} not found on CelesTrak.")
        return

    observer = Topos(latitude_degrees=config['latitude'], 
                     longitude_degrees=config['longitude'], 
                     elevation_m=config['elevation'])
    ts = load.timescale()

    curses.wrapper(run_curses, selected_sat, observer, ts, config, args.sound)

if __name__ == "__main__":
    main()