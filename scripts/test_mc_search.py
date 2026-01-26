import os
import mediacloud.api

api_key = os.getenv("MEDIA_CLOUD_API_KEY", "dd563eaed4bc18df7dafc58327f2b06c78a9be2c")
directory = mediacloud.api.DirectoryApi(api_key)

print("Testing source_list with name_search...")
try:
    # Try searching for "BBC"
    response = directory.source_list(name_search="BBC")
    print(f"Found {len(response.get('results', []))} results for 'BBC'")
    if response.get('results'):
        print(f"First result: {response['results'][0]['name']} - {response['results'][0]['url_search_string']}")
except Exception as e:
    print(f"Error: {e}")
