import json
import os
import sys

# Add project root to path to import backend modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

def enrich_geojson():
    """
    Enriches backend/data/countries.geo.json with:
    1. 'aliases': List of alternative names (e.g. 'United States', 'US', 'America').
    2. 'name_zh': Chinese name (e.g. '美国').
    """
    
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    geo_path = os.path.join(base_dir, 'data', 'countries.geo.json')
    
    if not os.path.exists(geo_path):
        print(f"Error: {geo_path} not found.")
        return

    # Dictionary of Enrichments (Code -> {name_zh, aliases})
    # This is a curated list for Major Powers and significant regions.
    # In a production system, this would come from a comprehensive library like pycountry or restcountries.
    enrichments = {
        'USA': {'name_zh': '美国', 'aliases': ['United States', 'US', 'U.S.', 'U.S.A.', 'America', 'United States of America']},
        'CHN': {'name_zh': '中国', 'aliases': ['China', 'PRC', 'P.R.C.', 'Mainland China']},
        'JPN': {'name_zh': '日本', 'aliases': ['Japan', 'Nippon']},
        'GBR': {'name_zh': '英国', 'aliases': ['United Kingdom', 'UK', 'U.K.', 'Great Britain', 'Britain']},
        'FRA': {'name_zh': '法国', 'aliases': ['France', 'French Republic']},
        'DEU': {'name_zh': '德国', 'aliases': ['Germany', 'Deutschland', 'German Federal Republic']},
        'RUS': {'name_zh': '俄罗斯', 'aliases': ['Russia', 'Russian Federation']},
        'IND': {'name_zh': '印度', 'aliases': ['India']},
        'KOR': {'name_zh': '韩国', 'aliases': ['South Korea', 'Korea', 'Republic of Korea', 'ROK']},
        'PRK': {'name_zh': '朝鲜', 'aliases': ['North Korea', 'DPRK']},
        'TWN': {'name_zh': '台湾', 'aliases': ['Taiwan', 'ROC', 'Republic of China']},
        'HKG': {'name_zh': '香港', 'aliases': ['Hong Kong', 'HK']},
        'CAN': {'name_zh': '加拿大', 'aliases': ['Canada']},
        'AUS': {'name_zh': '澳大利亚', 'aliases': ['Australia']},
        'BRA': {'name_zh': '巴西', 'aliases': ['Brazil', 'Brasil']},
        'ITA': {'name_zh': '意大利', 'aliases': ['Italy', 'Italia']},
        'ESP': {'name_zh': '西班牙', 'aliases': ['Spain', 'Espana']},
        'ISR': {'name_zh': '以色列', 'aliases': ['Israel']},
        'UKR': {'name_zh': '乌克兰', 'aliases': ['Ukraine']},
        'TUR': {'name_zh': '土耳其', 'aliases': ['Turkey', 'Turkiye']},
        'SAU': {'name_zh': '沙特阿拉伯', 'aliases': ['Saudi Arabia', 'Saudi', 'KSA']},
        'IRN': {'name_zh': '伊朗', 'aliases': ['Iran']},
        'IDN': {'name_zh': '印度尼西亚', 'aliases': ['Indonesia']},
        'SGP': {'name_zh': '新加坡', 'aliases': ['Singapore']},
        'MYS': {'name_zh': '马来西亚', 'aliases': ['Malaysia']},
        'VNM': {'name_zh': '越南', 'aliases': ['Vietnam']},
        'PHL': {'name_zh': '菲律宾', 'aliases': ['Philippines']},
        'THA': {'name_zh': '泰国', 'aliases': ['Thailand']},
    }

    print("Loading GeoJSON...")
    with open(geo_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    updated_count = 0
    for feature in data['features']:
        code = feature.get('id')
        props = feature.get('properties', {})
        
        if code in enrichments:
            enrich_data = enrichments[code]
            
            # Add name_zh
            if 'name_zh' in enrich_data:
                props['name_zh'] = enrich_data['name_zh']
            
            # Add aliases (merge with existing name if needed, but usually we just add the list)
            # We store aliases as a list in properties for easy access by Python
            if 'aliases' in enrich_data:
                props['aliases'] = enrich_data['aliases']
            
            updated_count += 1
    
    print(f"Enriched {updated_count} countries.")
    
    print("Saving GeoJSON...")
    with open(geo_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print("Done.")

if __name__ == "__main__":
    enrich_geojson()
