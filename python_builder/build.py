import os
from jinja2 import Environment, FileSystemLoader
from csscompressor import compress as compress_css
from jsmin import jsmin

# Configuration
BASE_DIR = os.path.dirname(__file__) # Use relative path for portability
SRC_DIR = os.path.join(BASE_DIR, 'src')
TEMPLATE_DIR = os.path.join(SRC_DIR, 'templates')
STATIC_DIR = os.path.join(SRC_DIR, 'static')
OUTPUT_DIR = os.path.join(BASE_DIR, '..', 'dist') # Output to dist folder in root

def ensure_dir(directory):
    if not os.path.exists(directory):
        os.makedirs(directory)

def read_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

def build():
    print("🚀 Starting Build Process...")
    ensure_dir(OUTPUT_DIR)

    # 1. Process CSS - Combine all CSS files
    print("🎨 Processing CSS...")
    css_content = read_file(os.path.join(STATIC_DIR, 'css', 'style.css'))
    research_css = read_file(os.path.join(STATIC_DIR, 'css', 'research-enhancement.css'))
    enhanced_css = read_file(os.path.join(STATIC_DIR, 'css', 'enhanced-ui.css'))
    combined_css = css_content + "\n" + research_css + "\n" + enhanced_css
    minified_css = compress_css(combined_css)
    
    # 2. Process JS - Combine all JS files
    print("📜 Processing JS...")
    # Order matters! data -> simulator -> map -> app
    # Using ENHANCED versions as primary, removing original conflicting files
    js_files = ['data.js', 'simulator.js', 'map-enhanced.js', 'app-enhanced.js']
    combined_js = ""
    for js_file in js_files:
        content = read_file(os.path.join(STATIC_DIR, 'js', js_file))
        combined_js += content + "\n"
    
    minified_js = jsmin(combined_js)

    # 3. Render HTML
    print("🏗️  Rendering HTML...")
    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
    template = env.get_template('index.html')
    
    output_html = template.render(
        title="Global Misspellings Lens V3.2 [Enhanced Research Edition]",
        app_name="GLOBAL LENS",
        version="V3.2-ENHANCED",
        css_content=minified_css,
        js_content=minified_js
    )

    # 4. Write Output
    output_path = os.path.join(OUTPUT_DIR, 'index.html')
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(output_html)

    print(f"✅ Build Complete! Output: {output_path}")
    print(f"   CSS Size: {len(combined_css)} -> {len(minified_css)} bytes")
    print(f"   JS Size:  {len(combined_js)} -> {len(minified_js)} bytes")
    print("   Features: Enhanced UI, Timeline System, Dynamic Heatmap, 194 UNESCO countries")

if __name__ == "__main__":
    build()