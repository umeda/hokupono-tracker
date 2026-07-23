import curses
import argparse
import numpy as np
from skyfield.api import Topos, load
from datetime import datetime, timedelta

# --- CONFIGURATION ---
MY_LAT = 19.49       
MY_LON = -155.92
MY_ELEVATION = 400
BASE_FREQ_MHZ = 437.800
C_MS = 299792458
# ---------------------

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

def get_data(iss, observer, ts, step_khz):
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

def run_curses(stdscr, iss, observer, ts, step_khz):
    curses.curs_set(0)
    stdscr.nodelay(True)
    stdscr.timeout(1000)

    next_aos_t = None
    last_aos_check = datetime.min

    while True:
        stdscr.clear()
        data = get_data(iss, observer, ts, step_khz)
        
        stdscr.addstr(1, 2, f"--- ISS LIVE TRACKER ({step_khz}kHz Steps) ---", curses.A_BOLD)
        stdscr.addstr(3, 4, f"Local Time:     {data['time'].strftime('%H:%M:%S')}")
        stdscr.addstr(4, 4, f"Elevation:      {data['alt']:.2f}°")
        stdscr.addstr(5, 4, f"Azimuth:        {data['az']:.2f}°")
        
        doppler_str = f"Doppler Shift:  {data['shift_raw']:+.3f} kHz "
        tune_str = f"(tune {data['tuned_freq']:.3f} MHz)"
        stdscr.addstr(7, 4, doppler_str + tune_str, curses.A_YELLOW if data['alt'] > 0 else curses.A_NORMAL)
        
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
    parser = argparse.ArgumentParser()
    parser.add_argument("-mode", choices=["curses"])
    parser.add_argument("-step", type=float, default=5.0)
    args = parser.parse_args()

    satellites = load.tle_file('https://celestrak.org/NORAD/elements/stations.txt')
    iss = {sat.name: sat for sat in satellites}['ISS (ZARYA)']
    observer = Topos(latitude_degrees=MY_LAT, longitude_degrees=MY_LON, elevation_m=MY_ELEVATION)
    ts = load.timescale()

    if args.mode == "curses":
        curses.wrapper(run_curses, iss, observer, ts, args.step)
    else:
        # Standard one-shot
        data = get_data(iss, observer, ts, args.step)
        print(f"Alt: {data['alt']:.2f}° | Tune: {data['tuned_freq']:.3f} MHz")

if __name__ == "__main__":
    main()