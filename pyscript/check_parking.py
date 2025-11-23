import re
import datetime
import time
import sys

# Add native Python module directory to sys.path
if "/config/pyscript_modules" not in sys.path:
    sys.path.append("/config/pyscript_modules")

# Import native Python module (runs at compiled speed with full Python features)
import parking_utils

@service
def check_parking(email_body=None, car_location=None, verbose_logging=False):
    # --- LOGGING ---
    def log_debug(msg):
        if verbose_logging: log.info(f"🅿️ [DEBUG] {msg}")
    def log_error(msg):
        log.error(f"🅿️ [ERROR] {msg}")

    # --- SETUP ---
    CACHE_FILE = "/config/parking_email_cache.txt"
    GEO_CACHE_FILE = "/config/parking_geo_cache.json"
    
    input_summary = f"Length: {len(str(email_body))}" if email_body else "None"
    log.info(f"🅿️ STARTING CHECK. Location: '{car_location}'. Input: {input_summary}")

    # Containers
    my_active, my_upcoming = [], []
    all_active, all_upcoming = [], []
    map_data = []
    is_danger_now, is_danger_soon = False, False
    final_status = "OK"
    email_timestamp = None

    try:
        # --- 1. LOAD EMAIL DATA ---
        final_email_body = None

        # Priority A: Direct Input (Write to disk via module)
        if email_body and len(str(email_body)) > 10:
            log_debug("Source: Direct Input. Saving via parking_utils...")
            # Use task.executor for blocking file I/O
            task.executor(parking_utils.save_text, CACHE_FILE, str(email_body))
            final_email_body = str(email_body)

            # Extract email date from Subject or Date header
            subject_match = re.search(r'Subject:.*?(\d{2}/\d{2}/\d{4})', str(email_body), re.IGNORECASE)
            date_match = re.search(r'Date:\s*(.+?)(?:\n|$)', str(email_body), re.IGNORECASE | re.MULTILINE)

            if subject_match:
                # Parse date from subject (21/11/2025 format)
                date_str = subject_match.group(1)
                try:
                    dt = datetime.datetime.strptime(date_str, "%d/%m/%Y")
                    email_timestamp = dt.strftime("%d %b %Y")
                except:
                    email_timestamp = date_str
            elif date_match:
                # Parse from Date header (Fri, 21 Nov 2025 23:16:58 +0000 format)
                date_str = date_match.group(1).strip()
                try:
                    # Try parsing email date format
                    from email.utils import parsedate_to_datetime
                    dt = parsedate_to_datetime(date_str)
                    email_timestamp = dt.strftime("%d %b %Y, %H:%M")
                except:
                    email_timestamp = date_str
            else:
                email_timestamp = datetime.datetime.now().strftime("%d %b %Y")

        # Priority B: Cache (Read from disk via module)
        else:
            log_debug("Source: Checking cache via parking_utils...")
            # Use task.executor for blocking file I/O
            cached = task.executor(parking_utils.read_text, CACHE_FILE)
            if cached and len(cached) > 10:
                log_debug("Cache Hit.")
                final_email_body = cached
                # Keep existing email timestamp if using cached data
                try:
                    attrs = state.getattr('binary_sensor.car_in_suspended_bay')
                    email_timestamp = attrs.get('email_data_date') if attrs else None
                    if not email_timestamp or email_timestamp == 'Unknown':
                        email_timestamp = 'No email received yet'
                except:
                    email_timestamp = 'No email received yet'
            else:
                log_debug("Cache Empty.")

        # --- 2. VALIDATION ---
        if not final_email_body:
            final_status = "Cache Empty"
            log_error(final_status)
            err_text = "_⚠️ System Empty. Forward a suspension email to yourself to initialize._"
            all_active, all_upcoming = [err_text], [err_text]
        
        elif not car_location:
            final_status = "No Location"
        
        else:
            # --- 3. LOGIC ---
            today = datetime.datetime.now().date()
            next_week = today + datetime.timedelta(days=7)
            
            # Load Geo Cache (use task.executor for file I/O)
            geo_cache = task.executor(parking_utils.read_json, GEO_CACHE_FILE)
            geo_updated = False

            # Helper to calculate distance between coordinates (in meters)
            def calc_distance(coord1, coord2):
                if not coord1 or not coord2: return None
                from math import radians, sin, cos, sqrt, atan2
                lat1, lon1 = radians(coord1[0]), radians(coord1[1])
                lat2, lon2 = radians(coord2[0]), radians(coord2[1])
                dlat, dlon = lat2 - lat1, lon2 - lon1
                a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
                c = 2 * atan2(sqrt(a), sqrt(1-a))
                return 6371000 * c  # Earth radius in meters

            # -- Geocode Car --
            car_coords = geo_cache.get(car_location)
            if not car_coords:
                log_debug(f"Geocoding Car (Network): {car_location}")
                # Use task.executor for blocking network I/O
                car_coords = task.executor(parking_utils.geocode, car_location)
                if car_coords:
                    geo_cache[car_location] = car_coords
                    geo_updated = True
                    task.sleep(1) # Rate limiting for geocoding API
            
            if car_coords:
                service.call("device_tracker", "see", dev_id="parking_monitor_car", gps=car_coords)

            # -- Parse Email --
            # (Local regex logic works fine in Pyscript)
            def parse_input(u):
                m = re.search(r'(\d+)', u)
                n = int(m.group(1)) if m else None
                s = re.sub(r'\d+', '', u).replace(',', '').strip().lower()
                return s, n

            def extract_nums(t):
                n = set()
                c = re.sub(r'\bNo\.?\s+(\d+)', r'\1', t, flags=re.IGNORECASE)
                for d in [".", " Sign", " Signs"]: 
                    if d in c: c = c.split(d)[0]
                p = re.compile(r'(\d+)\s*(?:-|to)\s*(\d+)', re.IGNORECASE)
                for m in p.finditer(c):
                    try: n.update(range(int(m.group(1)), int(m.group(2)) + 1))
                    except: continue
                c = p.sub(' ', c)
                p2 = re.compile(r'\b(\d+)\b(?!\s*(?:bays|spaces|permit|RES|PBP|sign|lamp|st|nd|rd|th))', re.IGNORECASE)
                for m in p2.finditer(c):
                    try: n.add(int(m.group(1)))
                    except: continue
                return n

            def get_dates(t):
                f, t_d = None, None
                pat = r'(\d{2}/\d{2}/\d{4})'
                m1 = re.search(r'From Date:\s*' + pat, t)
                if m1: 
                    try: f = datetime.datetime.strptime(m1.group(1), "%d/%m/%Y").date()
                    except: pass
                m2 = re.search(r'To Date:\s*' + pat, t)
                if m2:
                    try: t_d = datetime.datetime.strptime(m2.group(1), "%d/%m/%Y").date()
                    except: pass
                return f, t_d

            u_street, u_num = parse_input(car_location)
            
            decoded = str(final_email_body)
            decoded = decoded.replace('=\r\n', '').replace('=\n', '').replace('=3D', '=').replace('=20', ' ')
            decoded = re.sub(r'^>+\s*', '', decoded, flags=re.MULTILINE)
            decoded = re.sub(r'<[^>]+>', '', decoded)
            decoded = " ".join(decoded.split())
            
            blocks = decoded.split('APPROVED SUSPENSION')

            for i, block in enumerate(blocks):
                if i == 0: continue
                
                street_m = re.search(r'Street Name:\s*(.*?)(?:From Date|To Date|Number of Bays|$)', block, re.IGNORECASE)
                if street_m:
                    s_display = street_m.group(1).strip()
                    s_lower = s_display.lower()
                    
                    loc_desc = "Check Signage"
                    lm = re.search(r'Location:\s*(.*?)(?:To view|http|$)', block, re.IGNORECASE)
                    if lm: loc_desc = lm.group(1).strip()

                    f_date, t_date = get_dates(block)
                    if f_date and t_date:
                        entry = f"- **{s_display}**: {loc_desc} ({f_date.strftime('%d/%m')} - {t_date.strftime('%d/%m')})"
                        
                        # Map Data - create best geocoding address
                        geo_addr = s_display
                        nums = extract_nums(loc_desc)
                        if nums:
                            # Use street number if available
                            geo_addr = f"{min(nums)} {s_display}"
                        else:
                            # Try to extract landmark/building name
                            landmark_match = re.search(r'(?:outside|near|opposite|at)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)', loc_desc, re.IGNORECASE)
                            if landmark_match:
                                landmark = landmark_match.group(1)
                                geo_addr = f"{landmark}, {s_display}"
                        
                        sus_type = None
                        if f_date <= today <= t_date: 
                            all_active.append(entry)
                            sus_type = "active"
                        elif today < f_date: 
                            all_upcoming.append(entry)
                            sus_type = "upcoming"
                        
                        if sus_type:
                            map_data.append({"addr": geo_addr, "type": sus_type, "desc": loc_desc, "street": s_display})

                        # Risk Detection
                        if u_street and (u_street in s_lower or s_lower in u_street):
                            hit = False
                            # Match by house number if both have numbers
                            if nums and u_num and u_num in nums:
                                hit = True
                            # If user has no number, match any suspension on that street
                            elif u_num is None:
                                hit = True
                            # If suspension has no numbers, defer to distance check after geocoding
                            # (don't add to my_active yet - will check distance later)

                            if hit:
                                if f_date <= today <= t_date:
                                    my_active.append(f"{s_display}: {loc_desc}")
                                    is_danger_now = True
                                elif today < f_date <= next_week:
                                    my_upcoming.append(f"{s_display}: {loc_desc}")
                                    is_danger_soon = True

            # -- Geocode Suspensions (Top 5 Active) --
            active_sus = [s for s in map_data if s['type'] == 'active'][:5]
            for idx, sus in enumerate(active_sus):
                coords = geo_cache.get(sus['addr'])
                if not coords:
                    log_debug(f"Geocoding Sus {idx} (Network): {sus['addr']}")
                    # Use task.executor for blocking network I/O
                    coords = task.executor(parking_utils.geocode, sus['addr'])
                    if coords:
                        geo_cache[sus['addr']] = coords
                        geo_updated = True
                        task.sleep(1) # Rate limiting for geocoding API

                if coords:
                    service.call("device_tracker", "see",
                        dev_id=f"sus_active_{idx}", gps=coords,
                        attributes={"friendly_name": f"Suspension: {sus['desc'][:20]}..."})

                    # Distance-based risk check (within 100m = same block)
                    if car_coords and sus['street'].lower() in car_location.lower():
                        distance = calc_distance(car_coords, coords)
                        if distance and distance <= 100:
                            # Refine risk lists based on proximity
                            sus_desc = f"{sus['street']}: {sus['desc']}"
                            if sus_desc not in my_active:
                                my_active.append(sus_desc)
                                is_danger_now = True
                                log_debug(f"Distance alert: {distance:.0f}m from suspension")

            # Save Geo Cache (use task.executor for file I/O)
            if geo_updated:
                task.executor(parking_utils.save_json, GEO_CACHE_FILE, geo_cache)

    except Exception as e:
        final_status = f"Script Crash: {e}"
        log_error(final_status)

    # 4. OUTPUT
    log.info(f"🅿️ DONE. Status: {final_status}")
    state.set(
        "binary_sensor.car_in_suspended_bay",
        "on" if is_danger_now else "off",
        new_attributes={
            'friendly_name': 'Car in Suspended Bay',
            'device_class': 'problem',
            'active_suspensions': "\n".join(my_active) if my_active else "None",
            'upcoming_suspensions': "\n".join(my_upcoming) if my_upcoming else "None",
            'upcoming_risk': is_danger_soon,
            'all_active_suspensions': "\n".join(all_active) if all_active else "_No active suspensions found_",
            'all_upcoming_suspensions': "\n".join(all_upcoming) if all_upcoming else "_No upcoming suspensions found_",
            'last_status': final_status,
            'email_data_date': email_timestamp or 'Unknown',
            'last_checked': datetime.datetime.now().strftime("%d %b %Y, %H:%M")
        }
    )