
import sys
import os

# Add backend to path to import data
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from backend.data import DATA
    from backend.fips_country_map import FIPS_TO_ISO3
except ImportError:
    print("Error importing data modules")
    sys.exit(1)

print(f"Total countries in DATA: {len(DATA['COUNTRIES'])}")
print(f"Total mappings in FIPS_TO_ISO3: {len(FIPS_TO_ISO3)}")

data_iso_codes = {c["code"]: c for c in DATA["COUNTRIES"]}
mapped_iso_codes = set(FIPS_TO_ISO3.values())

# Check for missing countries in DATA
missing_in_data = []
for iso in mapped_iso_codes:
    if iso not in data_iso_codes:
        missing_in_data.append(iso)

print(f"ISO codes from FIPS map missing in DATA: {len(missing_in_data)}")
if missing_in_data:
    print(f"Sample missing: {missing_in_data[:5]}")

# Check for invalid coordinates
invalid_coords = []
for c in DATA["COUNTRIES"]:
    if c.get("lat") == 0 and c.get("lng") == 0:
        invalid_coords.append(c["name"])
    if c.get("lat") is None or c.get("lng") is None:
        invalid_coords.append(c["name"])

print(f"Countries with 0,0 or None coordinates: {len(invalid_coords)}")
if invalid_coords:
    print(f"Sample invalid: {invalid_coords[:5]}")

# Sample check
samples = ["USA", "CHN", "GBR", "RUS", "AUS", "IND"]
print("\nSample Coordinates:")
for code in samples:
    if code in data_iso_codes:
        c = data_iso_codes[code]
        print(f"{code}: {c['lat']}, {c['lng']}")
    else:
        print(f"{code}: Not found")
