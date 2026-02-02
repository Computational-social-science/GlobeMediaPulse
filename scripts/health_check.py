
import sys
import os
import socket
import subprocess
import json
import importlib.util
from datetime import datetime

import time

# ANSI Colors
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"

def print_progress(iteration, total, prefix='', suffix='', decimals=1, length=40, fill='█'):
    """
    Call in a loop to create terminal progress bar
    """
    percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
    filled_length = int(length * iteration // total)
    bar = fill * filled_length + '-' * (length - filled_length)
    # Clear line before printing progress to avoid clutter if logs printed previously
    # But since we print logs sequentially, we just print the bar on a new line or same line?
    # To keep it simple and compatible with the log function:
    # We will print the bar at the END of the script or update it in place if possible.
    # Given the logs print newlines, a persistent bottom bar is hard without curses.
    # We will print the bar state *after* each check.
    print(f'\r{prefix} |{bar}| {percent}% {suffix}', end = '\r')
    if iteration == total: 
        print()

def log(status, message):
    # Clear the current line (progress bar) before printing log
    print(f"\r{' ' * 80}\r", end='')
    if status == "PASS":
        print(f"[{GREEN}PASS{RESET}] {message}")
    elif status == "FAIL":
        print(f"[{RED}FAIL{RESET}] {message}")
    elif status == "WARN":
        print(f"[{YELLOW}WARN{RESET}] {message}")
    elif status == "INFO":
        print(f"[{CYAN}INFO{RESET}] {message}")
    else:
        print(f"[{status}] {message}")

def check_port(host, port, service_name):
    # Try HTTP check first for web ports
    if port in [8002, 5173, 5174]:
        import urllib.request
        try:
            url = f"http://{host}:{port}/"
            # Special case for backend health endpoint if needed, but root is fine
            if port == 8002: url = f"http://{host}:{port}/health" # use health endpoint
            
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200 or response.status == 404: # 404 means server is up
                    log("PASS", f"{service_name} is reachable on {url}")
                    return True
        except Exception:
            # Fallback to socket check if HTTP fails (e.g. backend starting up)
            pass

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            # Try connecting to the host
            result = s.connect_ex((host, port))
            if result == 0:
                log("PASS", f"{service_name} is reachable on {host}:{port}")
                return True
            
            # If localhost failed, try 127.0.0.1 specifically if host was localhost
            if host == "localhost":
                 result = s.connect_ex(("127.0.0.1", port))
                 if result == 0:
                    log("PASS", f"{service_name} is reachable on 127.0.0.1:{port}")
                    return True

            log("WARN", f"{service_name} is NOT reachable on {host}:{port}")
            return False
    except Exception as e:
        log("FAIL", f"Error checking {service_name}: {e}")
        return False

def check_python_dependencies():
    # print("\n--- Checking Python Dependencies ---") # Removed to use new log style
    req_path = os.path.join("backend", "requirements.txt")
    if not os.path.exists(req_path):
        log("WARN", f"requirements.txt not found at {req_path}")
        return

    missing = []
    with open(req_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # Basic parsing for package name (ignoring versions for simple check)
            pkg = line.split("@")[0].split("==")[0].split(">=")[0].split("[")[0].strip()
            if not importlib.util.find_spec(pkg.replace("-", "_")): # handle some replacements like python-dotenv -> dotenv? No, usually names match or close enough
                # Try specific mappings
                if pkg == "python-dotenv": pkg_import = "dotenv"
                elif pkg == "psycopg2-binary": pkg_import = "psycopg2"
                elif pkg == "fake-useragent": pkg_import = "fake_useragent"
                elif pkg == "scikit-learn": pkg_import = "sklearn"
                elif pkg == "playwright-stealth": pkg_import = "playwright_stealth"
                elif pkg == "newspaper3k": pkg_import = "newspaper"
                elif pkg == "newspaper4k": pkg_import = "newspaper"
                elif pkg == "beautifulsoup4": pkg_import = "bs4"
                elif pkg == "python-whois": pkg_import = "whois"
                elif pkg == "PyMySQL": pkg_import = "pymysql"
                elif pkg == "geograpy3": pkg_import = "geograpy"
                else: pkg_import = pkg.replace("-", "_")
                
                if not importlib.util.find_spec(pkg_import):
                     # Double check via pip freeze if import fails (some packages imply different import names)
                     # But for speed, just logging potential issue
                     missing.append(pkg)
    
    if missing:
        log("WARN", f"Potential missing Python packages: {', '.join(missing)}")
        print(f"{YELLOW}Suggestion: Run 'pip install -r backend/requirements.txt'{RESET}")
    else:
        log("PASS", "All core Python dependencies appear to be installed.")

def check_node_environment():
    # print("\n--- Checking Node.js Environment ---")
    try:
        node_ver = subprocess.check_output(["node", "-v"], shell=True).decode().strip()
        log("PASS", f"Node.js is installed: {node_ver}")
    except:
        log("FAIL", "Node.js is not installed or not in PATH.")
        return

    if not os.path.exists(os.path.join("frontend", "node_modules")):
        log("FAIL", "frontend/node_modules not found.")
        print(f"{YELLOW}Suggestion: Run 'cd frontend && npm install'{RESET}")
    else:
        log("PASS", "frontend/node_modules exists.")

def check_postgres():
    # print("\n--- Checking PostgreSQL ---")
    # Try to connect using psycopg2
    try:
        import psycopg2
        db_url = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost:5433/globemediapulse")
        conn = psycopg2.connect(db_url)
        conn.close()
        log("PASS", "Successfully connected to PostgreSQL.")
    except ImportError:
        log("FAIL", "psycopg2 module not found.")
    except Exception as e:
        log("FAIL", f"Failed to connect to PostgreSQL: {e}")
        print(f"{YELLOW}Suggestion: Ensure Docker container is running or Postgres is started.{RESET}")

def check_redis():
    # print("\n--- Checking Redis ---")
    try:
        import redis
        redis_url = os.getenv("REDIS_URL", "").strip()
        if redis_url:
            r = redis.Redis.from_url(redis_url, socket_timeout=1)
        else:
            host = os.getenv("REDIS_HOST", "localhost")
            port = int(os.getenv("REDIS_PORT", 6380))
            r = redis.Redis(host=host, port=port, socket_timeout=1)
        if r.ping():
            log("PASS", "Successfully connected to Redis.")
    except ImportError:
        log("FAIL", "redis module not found.")
    except Exception as e:
        log("FAIL", f"Failed to connect to Redis: {e}")
        print(f"{YELLOW}Suggestion: Ensure Redis is running and REDIS_URL points to the correct port (default 6380).{RESET}")

def main():
    print(f"Globe Media Pulse Environment Health Check - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("================================================================")
    
    total_steps = 6
    current_step = 0
    
    print_progress(current_step, total_steps, prefix='Progress:', suffix='Initializing...', length=30)
    time.sleep(0.5)

    # Check Python Deps
    log("INFO", "Checking Python Environment...")
    check_python_dependencies()
    current_step += 1
    print_progress(current_step, total_steps, prefix='Progress:', suffix='Python Checked', length=30)
    time.sleep(0.2)
    
    # Check Node/Frontend
    log("INFO", "Checking Node.js Environment...")
    check_node_environment()
    current_step += 1
    print_progress(current_step, total_steps, prefix='Progress:', suffix='Node Checked', length=30)
    time.sleep(0.2)
    
    # Check Services
    log("INFO", "Checking Database Services...")
    check_postgres()
    current_step += 1
    print_progress(current_step, total_steps, prefix='Progress:', suffix='Postgres Checked', length=30)
    
    check_redis()
    current_step += 1
    print_progress(current_step, total_steps, prefix='Progress:', suffix='Redis Checked', length=30)
    time.sleep(0.2)
    
    log("INFO", "Checking Active Ports...")
    # Check if backend is running
    backend_up = check_port("localhost", 8002, "Backend API")
    current_step += 1
    print_progress(current_step, total_steps, prefix='Progress:', suffix='Backend Checked', length=30)
    
    # Check if frontend is running
    frontend_up = check_port("localhost", 5173, "Frontend Dev Server")
    current_step += 1
    print_progress(current_step, total_steps, prefix='Progress:', suffix='Frontend Checked', length=30)
    time.sleep(0.5)
    
    # Final newline to clear bar
    print()
    print("\n--- Summary & Recommendations ---")
    if not backend_up:
        print(f"{RED}[ACTION] Backend is NOT running.{RESET} Run: python -m backend.main")
    else:
        print(f"{GREEN}[OK] Backend is running.{RESET}")
        
    if not frontend_up:
        print(f"{RED}[ACTION] Frontend is NOT running.{RESET} Run: cd frontend && npm run dev")
    else:
        print(f"{GREEN}[OK] Frontend is running.{RESET}")

    if not backend_up or not frontend_up:
        print(f"\n{YELLOW}Note: Use separate terminals to run backend and frontend.{RESET}")

if __name__ == "__main__":
    # Ensure we are in project root for relative paths to work
    if os.path.basename(os.getcwd()) == "scripts":
        os.chdir("..")
    elif os.path.basename(os.getcwd()) == "backend":
        os.chdir("..")
        
    main()
