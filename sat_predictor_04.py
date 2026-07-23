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

def run_prediction(sat, observer, ts, config, eph):
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

    all_collected_passes = []
    for p in passes:
        reasons = []
        t_aos, t_max, t_los = p['aos'], p['max'], p['los']
        
        # Filter: Time of day (Check against Local System Time)
        dt_max_local = t_max.astimezone(local_tz)
        if not (config['earliest_hour'] <= dt_max_local.hour < config['latest_hour']):
            reasons.append("inconvenient time")

        # Coordinates
        # To get the position of the satellite relative to the observer,
        # we subtract the observer's position (Topos) from the satellite's position.
        # Skyfield handles the underlying coordinate system transformations.
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
        
        # Visibility Check: Sunlit satellite and observer in darkness (Sun below -6 deg altitude)
        # To get the Sun's position relative to the observer, we must first get the observer's
        # barycentric position, then observe the Sun from there.
        observer_barycentric = (eph['earth'] + observer).at(t_max)
        sun_alt = observer_barycentric.observe(eph['sun']).apparent().altaz()[0].degrees
        is_sunlit = sat.at(t_max).is_sunlit(eph)
        visible = is_sunlit and sun_alt < -6

        all_collected_passes.append({
            'name': sat.name,
            'aos': t_aos,
            'max': t_max,
            'los': t_los,
            'dt_max_local': dt_max_local,
            'pos_aos': pos_aos,
            'pos_max': pos_max,
            'pos_los': pos_los,
            'max_alt': max_alt,
            'max_az': max_az,
            'is_ascending': is_ascending,
            'is_retrograde': is_retrograde,
            'quality': quality,
            'is_visible': visible,
            'reasons': reasons,
            'local_tz': local_tz
        })
    return all_collected_passes

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
    eph = load('de421.bsp')

    print(f"\nScanning for passes over the next {config['search_days']} days...")
    
    # Determine which satellites to process
    if choice == 0:
        to_predict = sat_list
    elif 1 <= choice <= len(sat_list):
        to_predict = [sat_list[choice - 1]]
    else:
        print("Error: Invalid selection.")
        return

    all_passes = []
    for entry in to_predict:
        sat = get_tle(config, entry)
        if sat:
            all_passes.extend(run_prediction(sat, observer, ts, config, eph))

    # Sort all passes by time of AOS
    all_passes.sort(key=lambda x: x['aos'].tt)

    for p in all_passes:
        if p['quality'] == "low" and not show_filtered:
            continue

        type_str = "Ascending" if p['is_ascending'] else "Descending"
        orbit_str = "Retrograde" if p['is_retrograde'] else "Prograde"
        
        # Determine the ground path icon: / for SW->NE or SE->NW, \ for NW->SE or NE->SW
        icon = "/" if p['is_ascending'] != p['is_retrograde'] else "\\"
        # Format with ANSI inverse text codes (\033[7m) and reset (\033[0m)
        icon_display = f"\033[7m {icon} \033[0m"

        date_str = p['dt_max_local'].strftime('%b-%d')
        print(f"\n{date_str} | Satellite: {p['name']} ({type_str}, {orbit_str}, {icon_display}) - Quality: {p['quality']}{'*' if p['is_visible'] else ''}")
        if p['quality'] == "low":
            print(f"  Reason: {', '.join(p['reasons'])}")
        print(f"  AOS: {p['aos'].astimezone(p['local_tz']).strftime('%H:%M:%S')} @ {p['pos_aos'][1].degrees:3.0f}° Az")
        print(f"  MAX: {p['max'].astimezone(p['local_tz']).strftime('%H:%M:%S')} @ {p['max_alt']:2.1f}° Alt, {p['max_az']:3.0f}° Az")
        print(f"  LOS: {p['los'].astimezone(p['local_tz']).strftime('%H:%M:%S')} @ {p['pos_los'][1].degrees:3.0f}° Az")

if __name__ == "__main__":
    main()
