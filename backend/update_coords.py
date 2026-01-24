
import json
import re

# Safer visual centers for irregular/archipelago countries
OVERRIDES = {
    "USA": {"lat": 39.8283, "lng": -98.5795}, # Contiguous US Center
    "GBR": {"lat": 54.5, "lng": -2.0},        # UK Center (Pennines)
    "JPN": {"lat": 36.2, "lng": 138.2},       # Central Japan (Honshu)
    "PHL": {"lat": 15.5, "lng": 121.0},       # Luzon (Wider landmass)
    "IDN": {"lat": -1.0, "lng": 114.0},       # Kalimantan (Deep inland)
    "NZL": {"lat": -43.5, "lng": 171.5},      # South Island (Wider)
    "ITA": {"lat": 42.8, "lng": 12.6},        # Umbria (Central Italy)
    "GRC": {"lat": 39.5, "lng": 22.0},        # Thessaly (Mainland)
    "MYS": {"lat": 4.5, "lng": 102.0},        # Peninsular Malaysia
    "VNM": {"lat": 16.5, "lng": 107.5},       # Central Vietnam (Inland)
    "NOR": {"lat": 61.0, "lng": 9.0},         # Southern Norway (Wider)
    "CHL": {"lat": -33.5, "lng": -70.6},      # Central Chile (Santiago area)
    "HRV": {"lat": 45.5, "lng": 17.0},        # Slavonia (Inland)
    "PAN": {"lat": 8.5, "lng": -80.0},        # Central Panama
    "CUB": {"lat": 22.0, "lng": -79.5},       # Central Cuba
    "PRK": {"lat": 40.0, "lng": 127.0},       # Inland
    "KOR": {"lat": 36.5, "lng": 128.0},       # Inland
    "THA": {"lat": 15.0, "lng": 101.0},       # Central
    "SWE": {"lat": 62.0, "lng": 15.0},        # Inland
}

def update_file(path, is_js=False):
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Simple regex replace for each override
    # Pattern: "code": "USA",\s*"name": "[^"]*",\s*"lat": [\d.-]+,\s*"lng": [\d.-]+
    # We need to be careful with JSON structure
    
    count = 0
    for code, coords in OVERRIDES.items():
        # Regex to find the block for this country
        # We look for "code": "CODE" and then capture lat/lng lines
        # This handles both Python dict and JS object syntax roughly
        
        # Python/JSON: "code": "USA", ... "lat": X, "lng": Y
        pattern = re.compile(
            r'("code":\s*"' + code + r'",\s*"name":\s*"[^"]*",\s*"lat":\s*)([\d.-]+)(,\s*"lng":\s*)([\d.-]+)',
            re.DOTALL
        )
        
        match = pattern.search(content)
        if match:
            old_lat = match.group(2)
            old_lng = match.group(4)
            
            new_lat = str(coords["lat"])
            new_lng = str(coords["lng"])
            
            if old_lat != new_lat or old_lng != new_lng:
                # Replace
                # Group 1: prefix, Group 2: lat, Group 3: mid, Group 4: lng
                replacement = f'{match.group(1)}{new_lat}{match.group(3)}{new_lng}'
                # We need to replace the exact match in content
                # Since regex search finds the first one, and we assume unique codes
                # We can use sub() but sub() replaces all. 
                # Better to use string replacement on the matched span?
                # No, regex sub is safer if pattern is unique.
                
                content = content.replace(match.group(0), replacement)
                count += 1
                print(f"Updated {code}: {old_lat},{old_lng} -> {new_lat},{new_lng}")
    
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Saved {path} with {count} updates.")

import os

# ... existing code ...

if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    backend_data = os.path.join(base_dir, "backend", "core", "data.py")
    frontend_data = os.path.join(base_dir, "frontend", "src", "lib", "data.js")
    
    print(f"Updating {backend_data}...")
    if os.path.exists(backend_data):
        update_file(backend_data)
    else:
        print(f"File not found: {backend_data}")
        # Fallback to old location just in case
        old_backend = os.path.join(base_dir, "backend", "data.py")
        if os.path.exists(old_backend):
            print(f"Found at old location: {old_backend}")
            update_file(old_backend)
    
    print(f"Updating {frontend_data}...")
    if os.path.exists(frontend_data):
        update_file(frontend_data, is_js=True)
    else:
        print(f"File not found: {frontend_data}")
