from logging import config
import tomllib
import os
import urllib.parse
from skyfield.api import Topos, load
from datetime import datetime, timedelta

def get_tle(config, sat_entry):
    """Fetches TLE for a specific satellite using its NORAD ID from CelesTrak."""
    query_params = urllib.parse.urlencode({'CATNR': sat_entry['norad_id'], 'FORMAT': 'TLE'})
    search_url = f"{config['tle_url']}?{query_params}"
    try:
        # Force reload to ensure we get the specific satellite requested
        satellites = load.tle_file(search_url, reload=True)
        selected_sat = next((s for s in satellites if s.model.satnum == sat_entry['norad_id']), None)
        return selected_sat
    except Exception:
        return None

def run_prediction(sat, observer, ts, config, show_filtered):
    """Calculates and filters passes for a single satellite."""
    t0 = ts.now()
    # Get the local timezone once to use for all astimezone() calls
    local_tz = datetime.now().astimezone().tzinfo
    t1 = t0 + timedelta(days=config['search_days'])

    # Find passes (returns times of AOS, Max Elevation, and LOS)
    times, events = sat.find_events(observer, t0, t1, altitude_degrees=0)
    
    passes = []
    current_pass = {}
    for t, event in zip(times, events):
        if event == 0:
            current_pass = {'aos': t}
        elif event == 1 and 'aos' in current_pass:
            current_pass['max'] = t
        elif event == 2 and 'max' in current_pass:
            current_pass['los'] = t
            passes.append(current_pass)
            current_pass = {}

    for p in passes:
        reasons = []
        t_aos, t_max, t_los = p['aos'], p['max'], p['los']
        
        # Filter: Time of day (Check against Local System Time)
        dt_max_local = t_max.astimezone(local_tz)
        if not (config['earliest_hour'] <= dt_max_local.hour < config['latest_hour']):
            reasons.append("inconvenient time")

        # Coordinates
        diff = sat - observer
        pos_aos = diff.at(t_aos).altaz()
        pos_max = diff.at(t_max).altaz()
        pos_los = diff.at(t_los).altaz()

        max_alt = pos_max[0].degrees
        max_az = pos_max[1].degrees

        # Filter: Minimum peak elevation
        if max_alt < config['min_elevation']:
            reasons.append("too low")
            
        # Direction Detection
        sub_aos = sat.at(t_aos).subpoint()
        sub_later = sat.at(ts.from_datetime(t_aos.utc_datetime() + timedelta(minutes=1))).subpoint()
        is_ascending = sub_later.latitude.degrees > sub_aos.latitude.degrees

        # Directional Side Filtering
        is_retrograde = sat.model.inclo > 1.5708  # Inclination > 90 degrees (pi/2 radians)
        if is_retrograde:
            # Retrograde: Ascending passes are SW, Descending are NW
            if (is_ascending and not (180 <= max_az <= 270)) or \
               (not is_ascending and not (270 <= max_az <= 360)):
                reasons.append("obscured direction")
        else:
            # Prograde: Ascending passes are NW, Descending are SW
            if (is_ascending and not (270 <= max_az <= 360)) or \
               (not is_ascending and not (180 <= max_az <= 270)):
                reasons.append("obscured direction")

        quality = "high" if not reasons else "low"
        
        if quality == "low" and not show_filtered:
            continue

        type_str = "Ascending" if is_ascending else "Descending"
        date_str = dt_max_local.strftime('%b-%d')
        print(f"\n{date_str} | Satellite: {sat.name} ({type_str}) - Quality: {quality}")
        if quality == "low":
            print(f"  Reason: {', '.join(reasons)}")
        print(f"  AOS: {t_aos.astimezone(local_tz).strftime('%H:%M:%S')} @ {pos_aos[1].degrees:3.0f}° Az")
        print(f"  MAX: {t_max.astimezone(local_tz).strftime('%H:%M:%S')} @ {max_alt:2.1f}° Alt, {max_az:3.0f}° Az")
        print(f"  LOS: {t_los.astimezone(local_tz).strftime('%H:%M:%S')} @ {pos_los[1].degrees:3.0f}° Az")

def main():
    # Load configuration
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, 'tracker.toml')
    with open(config_path, 'rb') as f:
        config = tomllib.load(f)

    # User Interface for Satellite Selection
    sat_list = config['satellites']
    print("Available satellites (from tracker.toml):")
    print("0: All Satellites")
    for i, entry in enumerate(sat_list, 1):
        print(f"{i}: {entry['name']} (NORAD {entry['norad_id']})")
    
    try:
        val = input(f"\nSelect a satellite (0-{len(sat_list)}): ")
        choice = int(val)
    except (ValueError, EOFError, KeyboardInterrupt):
        return

    show_filtered = config.get('show_filtered_passes', False)

    # Setup Skyfield
    observer = Topos(latitude_degrees=config['latitude'], 
                     longitude_degrees=config['longitude'], 
                     elevation_m=config['elevation'])
    ts = load.timescale()

    print(f"\nScanning for passes over the next {config['search_days']} days...")
    
    # Determine which satellites to process
    if choice == 0:
        to_predict = sat_list
    elif 1 <= choice <= len(sat_list):
        to_predict = [sat_list[choice - 1]]
    else:
        print("Error: Invalid selection.")
        return

    for entry in to_predict:
        sat = get_tle(config, entry)
        if sat:
            run_prediction(sat, observer, ts, config, show_filtered)

if __name__ == "__main__":
    main()
