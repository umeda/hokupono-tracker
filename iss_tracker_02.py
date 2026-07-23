import curses
import time
import argparse
from skyfield.api import Topos, load
from datetime import datetime
import numpy as np

# --- CONFIGURATION ---
MY_LAT = 19.55          # North is positive, South is negative
MY_LON = -155.93        # East is positive, West is negative
MY_ELEVATION = 438      # Elevation in meters
ISS_FREQ_MHZ = 437.800  # Standard ISS Downlink
C_MS = 299792458        # Speed of light in m/s
# ---------------------

def get_data(iss, observer, ts):
    t = ts.now()
    # Calculate the vector from observer to ISS
    difference = iss - observer
    topocentric = difference.at(t)
    
    # Get Alt/Az
    alt, az, distance = topocentric.altaz()
    
    # --- FIXED DOPPLER CALCULATION ---
    # Get relative velocity vector
    # .velocity.km_per_s gives (vx, vy, vz) relative to the observer
    v_vector = topocentric.velocity.km_per_s
    # Get relative position vector (unit vector)
    p_vector = topocentric.position.km / distance.km
    
    # Range rate is the projection of velocity onto the position vector
    # Positive = moving away, Negative = approaching
    range_rate_km_s = np.dot(v_vector, p_vector)
    range_rate_m_s = range_rate_km_s * 1000.0
    
    # Doppler formula
    doppler_freq = ISS_FREQ_MHZ * (1 - (range_rate_m_s / C_MS))
    shift_khz = (doppler_freq - ISS_FREQ_MHZ) * 1000
    
    return {
        "time": datetime.now().strftime('%H:%M:%S'),
        "alt": alt.degrees,
        "az": az.degrees,
        "range_rate": range_rate_km_s, 
        "shift": shift_khz
    }

def run_curses(stdscr, iss, observer, ts):
    curses.curs_set(0) # Hide cursor
    stdscr.nodelay(True) # Non-blocking input
    stdscr.timeout(3000) # Refresh every 3 seconds

    while True:
        stdscr.clear()
        data = get_data(iss, observer, ts)
        
        stdscr.addstr(1, 2, "--- ISS LIVE TRACKER (Press 'q' to quit) ---", curses.A_BOLD)
        stdscr.addstr(3, 4, f"Local Time:     {data['time']}")
        stdscr.addstr(4, 4, f"Elevation:      {data['alt']:.2f}°")
        stdscr.addstr(5, 4, f"Azimuth:        {data['az']:.2f}°")
        stdscr.addstr(6, 4, f"Range Rate:     {data['range_rate']:.3f} km/s")
        stdscr.addstr(7, 4, f"Doppler Shift:  {data['shift']:.3f} kHz (@ {ISS_FREQ_MHZ:.3f} MHz)")
        
        status = "VISIBLE" if data['alt'] > 0 else "BELOW HORIZON"
        stdscr.addstr(9, 4, f"STATUS: {status}", curses.A_REVERSE if data['alt'] > 0 else curses.A_NORMAL)
        
        stdscr.refresh()
        
        if stdscr.getch() == ord('q'):
            break

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-mode", choices=["curses"], help="Display in ncurses table")
    args = parser.parse_args()

    # Setup Skyfield
    stations_url = 'https://celestrak.org/NORAD/elements/stations.txt'
    satellites = load.tle_file(stations_url)
    iss = {sat.name: sat for sat in satellites}['ISS (ZARYA)']
    observer = Topos(latitude_degrees=MY_LAT, longitude_degrees=MY_LON, elevation_m=MY_ELEVATION)
    ts = load.timescale()

    if args.mode == "curses":
        curses.wrapper(run_curses, iss, observer, ts)
    else:
        # Standard one-shot print
        data = get_data(iss, observer, ts)
        print(f"Time: {data['time']} | Alt: {data['alt']:.2f}° | Az: {data['az']:.2f}° | Shift: {data['shift']:.2f} kHz")

if __name__ == "__main__":
    main()