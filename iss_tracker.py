from skyfield.api import Topos, load
from datetime import datetime

# --- CONFIGURATION ---
# Replace these with your actual coordinates
MY_LAT = 19.55          # North is positive, South is negative
MY_LON = -155.93         # East is positive, West is negative
MY_ELEVATION = 438     # Elevation in meters
# ---------------------

def get_iss_position():
    # 1. Load the latest ISS TLE data from CelesTrak
    stations_url = 'https://celestrak.org/NORAD/elements/stations.txt'
    satellites = load.tle_file(stations_url)
    
    # Filter for the ISS (usually named 'ISS (ZARYA)')
    by_name = {sat.name: sat for sat in satellites}
    iss = by_name['ISS (ZARYA)']

    # 2. Define your observer location
    observer = Topos(latitude_degrees=MY_LAT, 
                     longitude_degrees=MY_LON, 
                     elevation_m=MY_ELEVATION)

    # 3. Get the current time
    ts = load.timescale()
    t = ts.now()

    # 4. Calculate the relative position
    # This subtracts the observer's position from the ISS's position
    difference = iss - observer
    topocentric = difference.at(t)

    # 5. Get Azimuth and Elevation
    alt, az, distance = topocentric.altaz()

    return alt, az

if __name__ == "__main__":
    altitude, azimuth = get_iss_position()
    
    print(f"--- ISS Current Position (Local) ---")
    print(f"Time:      {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Elevation: {altitude.degrees:.2f}°")
    print(f"Azimuth:   {azimuth.degrees:.2f}° ({azimuth.degrees:>3.0f}°)")
    
    # Interpretation
    if altitude.degrees > 0:
        print("\nSTATUS: The ISS is currently ABOVE your horizon! 🛰️")
    else:
        print("\nSTATUS: The ISS is currently below the horizon.")

