import os
import json
import urllib.request
import urllib.parse

# These functions run in standard Python, bypassing Pyscript restrictions.

def save_text(path, content):
    """Saves string content to a file."""
    try:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(str(content))
        return True
    except Exception as e:
        print(f"ParkingUtils Error writing text: {e}")
        return False

def read_text(path):
    """Reads string content from a file."""
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            print(f"ParkingUtils Error reading text: {e}")
    return None

def save_json(path, content):
    """Saves a dictionary to a JSON file."""
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(content, f, indent=2)
        return True
    except Exception as e:
        print(f"ParkingUtils Error writing JSON: {e}")
        return False

def read_json(path):
    """Reads a dictionary from a JSON file."""
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"ParkingUtils Error reading JSON: {e}")
    return {}

def geocode(address):
    """
    Geocodes an address using Nominatim.
    This is blocking I/O, intended to be run via task.executor.
    """
    try:
        query = f"{address}, Kensington and Chelsea, London, UK"
        params = urllib.parse.urlencode({'q': query, 'format': 'json', 'limit': 1})
        url = f"https://nominatim.openstreetmap.org/search?{params}"
        
        # User-Agent is required by Nominatim Terms of Service
        req = urllib.request.Request(url, headers={'User-Agent': 'HomeAssistant_Parking_Monitor/1.0'})
        
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            if data and len(data) > 0:
                return float(data[0]['lat']), float(data[0]['lon'])
    except Exception as e:
        print(f"ParkingUtils Geocode Error: {e}")
    return None