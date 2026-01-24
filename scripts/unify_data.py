import json
import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GEOJSON_PATH = ROOT / 'backend/data/countries.geo.json'
BACKEND_PATH = ROOT / 'backend/data.py'
FRONTEND_PATH = ROOT / 'frontend/src/lib/data.js'
BUILDER_PATH = ROOT / 'python_builder/src/static/js/data.js'
ROOT_JS_PATH = ROOT / 'js/data.js'

def get_centroid(geometry):
    # Very simple centroid calculation for Polygon/MultiPolygon
    # This is an approximation
    coords = []
    def extract_coords(geo_coords):
        if isinstance(geo_coords[0], (float, int)):
            return [geo_coords]
        flat = []
        for item in geo_coords:
            flat.extend(extract_coords(item))
        return flat

    if geometry['type'] == 'Polygon':
        # Polygon coordinates are list of rings, first is exterior
        ring = geometry['coordinates'][0]
        return calculate_ring_centroid(ring)
    elif geometry['type'] == 'MultiPolygon':
        # Average of centroids of largest rings of polygons? 
        # Or just all points. Let's do all points average for simplicity/robustness
        # or better: bounding box center
        all_points = []
        for poly in geometry['coordinates']:
             all_points.extend(poly[0]) # Outer ring
        return calculate_ring_centroid(all_points)
    return 0, 0

def calculate_ring_centroid(points):
    x = [p[0] for p in points]
    y = [p[1] for p in points]
    return sum(y) / len(y), sum(x) / len(x)

def load_existing_metadata():
    # Load backend data to preserve lat/lng/region if available
    try:
        content = BACKEND_PATH.read_text(encoding='utf-8')
        # Extract dictionary part
        start = content.find('DATA =')
        brace = content.find('{', start)
        # Simple brace counting
        count = 0
        end = -1
        for i, ch in enumerate(content[brace:], start=brace):
            if ch == '{': count += 1
            elif ch == '}': count -= 1
            if count == 0:
                end = i
                break
        data_dict = ast.literal_eval(content[brace:end+1])
        
        meta = {}
        for c in data_dict.get('COUNTRIES', []):
            meta[c['code']] = {
                'lat': c.get('lat'),
                'lng': c.get('lng'),
                'region': c.get('region', 'Unknown')
            }
        
        others = {k: v for k, v in data_dict.items() if k != 'COUNTRIES'}
        return meta, others
    except Exception as e:
        print(f"Warning: Could not load existing metadata: {e}")
        return {}, {}

def main():
    print(f"Loading GeoJSON from {GEOJSON_PATH}")
    geo_data = json.loads(GEOJSON_PATH.read_text(encoding='utf-8'))
    
    existing_meta, other_data = load_existing_metadata()
    
    new_countries = []
    
    for feature in geo_data['features']:
        code = feature.get('id')
        name = feature.get('properties', {}).get('name')
        
        if not code or not name:
            continue
            
        entry = {
            'code': code,
            'name': name,
        }
        
        # Preserve lat/lng/region or calculate/default
        if code in existing_meta:
            entry['lat'] = existing_meta[code]['lat']
            entry['lng'] = existing_meta[code]['lng']
            entry['region'] = existing_meta[code]['region']
        else:
            # Calculate from geometry
            lat, lng = get_centroid(feature['geometry'])
            entry['lat'] = round(lat, 6)
            entry['lng'] = round(lng, 6)
            entry['region'] = 'Unknown' # or try to infer?
            
        new_countries.append(entry)
    
    # Sort by name
    new_countries.sort(key=lambda x: x['name'])
    
    print(f"Processed {len(new_countries)} countries from GeoJSON")
    
    # 1. Update Backend
    update_backend(new_countries, other_data)
    
    # 2. Update Frontend
    update_js_file(FRONTEND_PATH, new_countries, other_data, is_export=True)
    
    # 3. Update Python Builder
    update_js_file(BUILDER_PATH, new_countries, other_data, is_export=False)
    
    # 4. Update Root JS (Subset)
    update_root_js(ROOT_JS_PATH, new_countries)

def update_backend(countries, other_data):
    # Reconstruct Python file
    # We want to format it nicely
    
    lines = ['DATA = {']
    lines.append('    "COUNTRIES": [')
    
    for i, c in enumerate(countries):
        comma = ',' if i < len(countries) - 1 else ''
        lines.append('        {')
        lines.append(f'            "code": "{c["code"]}",')
        lines.append(f'            "name": "{c["name"]}",')
        lines.append(f'            "lat": {c["lat"]},')
        lines.append(f'            "lng": {c["lng"]},')
        lines.append(f'            "region": "{c["region"]}"')
        lines.append(f'        }}{comma}')
    
    lines.append('    ],')
    
    # Add other data (KEYBOARD_ADJACENCY etc)
    # We can just repr them but formatted slightly better?
    # Or just dump json and adjust
    
    for key, value in other_data.items():
        json_str = json.dumps(value, indent=4)
        # Adjust indentation
        indented = '\n'.join('    ' + line for line in json_str.split('\n'))
        lines.append(f'\n    "{key}": {indented.strip()},')

    # Remove last comma if exists
    if lines[-1].endswith(','):
        lines[-1] = lines[-1][:-1]
        
    lines.append('}')
    
    BACKEND_PATH.write_text('\n'.join(lines), encoding='utf-8')
    print(f"Updated {BACKEND_PATH}")

def update_js_file(path, countries, other_data, is_export=False):
    prefix = "export const DATA = {" if is_export else "const DATA = {"
    
    lines = []
    # Try to preserve comments if any (simple approach: just read top lines?)
    # Actually, let's just overwrite with standard header
    if 'Expanded to' in path.read_text(encoding='utf-8'):
        lines.append(f"// Data Storage - Expanded to {len(countries)} UNESCO member countries")
    else:
        lines.append("// Data Storage")
        
    lines.append(prefix)
    lines.append('    COUNTRIES: [')
    
    for i, c in enumerate(countries):
        comma = ',' if i < len(countries) - 1 else ''
        # JS style: keys without quotes often preferred but consistent with previous
        # Previous files used: { code: "AFG", ... } (unquoted keys)
        lines.append(f'        {{ code: "{c["code"]}", name: "{c["name"]}", lat: {c["lat"]}, lng: {c["lng"]}, region: "{c["region"]}" }}{comma}')
        
    lines.append('    ],')
    
    # Other data
    for key, value in other_data.items():
        lines.append('')
        lines.append(f'    {key}: {{')
        if isinstance(value, dict):
             # KEYBOARD_ADJACENCY
             entries = []
             for k, v in value.items():
                 entries.append(f"        '{k}': '{v}'")
             lines.append(', '.join(entries)) # This might be too long for one line?
             # The original had multiline. Let's try to be smart.
             # Actually, let's just use json.dumps and strip quotes from keys if simple
             pass
        
        # Generic dumper for other data
        # We'll use json.dumps but key keys unquoted if possible?
        # Let's just use valid JSON for the value part
        json_str = json.dumps(value, indent=8)
        # Remove opening/closing braces of the main object to merge into our structure?
        # No, value is the object.
        # But we want keys unquoted.
        # Let's simple dump and regex replace
        formatted = json_str.replace('"', "'") # Replace double quotes with single? JS usually uses single or double.
        # Let's stick to valid JSON for values, it's valid JS too.
        # Just indentation needs fix
        indented = '\n'.join(line for line in json_str.split('\n'))
        # remove first/last line if it's just braces?
        # Actually, let's just manually write KEYBOARD_ADJACENCY and HEADLINES if we know them
        if key == 'KEYBOARD_ADJACENCY':
            # split into chunks
            items = list(value.items())
            chunk_size = 10
            for i in range(0, len(items), chunk_size):
                chunk = items[i:i+chunk_size]
                strs = [f"'{k}': '{v}'" for k,v in chunk]
                comma = ',' if i + chunk_size < len(items) else ''
                lines.append('        ' + ', '.join(strs) + comma)
        else:
             # HEADLINES
             lines.append(indented[1:-1].strip()) # strip outer braces? No wait.
             # Let's just dump it and indent
             json_lines = json.dumps(value, indent=4).split('\n')
             for jl in json_lines[1:-1]: # skip { and }
                 lines.append('    ' + jl)
                 
        lines.append('    }' + (',' if key != list(other_data.keys())[-1] else ''))

    lines.append('};')
    
    path.write_text('\n'.join(lines), encoding='utf-8')
    print(f"Updated {path}")

def update_root_js(path, countries):
    # This file has a subset.
    # Strategy: Read file, find which codes are present, update them.
    # Remove any codes that are NOT in the new list (unlikely).
    # Add any missing codes? No, keep it a subset.
    
    content = path.read_text(encoding='utf-8')
    
    # Extract current list
    # Assuming standard format
    m = re.search(r'COUNTRIES\s*:\s*\[(.*?)\]', content, re.S)
    if not m:
        print(f"Skipping {path}: could not find COUNTRIES array")
        return
        
    array_content = m.group(1)
    # Parse existing codes
    existing_codes = set()
    # simple regex for code: "..."
    for match in re.finditer(r'code\s*:\s*["\'](\w+)["\']', array_content):
        existing_codes.add(match.group(1))
        
    # Build new list based on existing codes, sorted by index in new list? or original order?
    # Let's use the new countries list but filter
    subset = [c for c in countries if c['code'] in existing_codes]
    
    # Reconstruct file
    # We'll just replace the COUNTRIES array content
    
    new_lines = []
    for i, c in enumerate(subset):
        comma = ',' if i < len(subset) - 1 else ''
        # Minimal fields for root JS? Check original.
        # Original: code, name, lat, lng. No region.
        new_lines.append(f'        {{ code: "{c["code"]}", name: "{c["name"]}", lat: {c["lat"]}, lng: {c["lng"]} }}{comma}')
        
    new_block = '\n'.join(new_lines)
    
    new_content = re.sub(r'COUNTRIES\s*:\s*\[.*?\]', f'COUNTRIES: [\n{new_block}\n    ]', content, flags=re.S)
    
    path.write_text(new_content, encoding='utf-8')
    print(f"Updated {path}")

if __name__ == '__main__':
    main()
