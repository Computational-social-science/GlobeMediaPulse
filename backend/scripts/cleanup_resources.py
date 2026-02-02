import os
import shutil
import logging
import glob
import tempfile

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def cleanup_temp_resources():
    """
    Cleans up temporary files to free up space on ephemeral runtimes.
    Target:
        - Scrapy/Playwright temporary directories.
        - Old log files.
        - Potential image artifacts.
    """
    logger.info("Starting Resource Cleanup...")
    
    # Define targets
    # Temp directories often used by libraries
    tmp_dir = tempfile.gettempdir()
    temp_patterns = [
        os.path.join(tmp_dir, "playwright*"),
        os.path.join(tmp_dir, "scrapy*"),
        os.path.join(tmp_dir, "pymp-*"), # Multiprocessing
        os.path.join(tmp_dir, ".X*-lock"),
        "./.scrapy/httpcache" # If enabled
    ]
    
    # Size threshold for logs (50MB)
    LOG_LIMIT = 50 * 1024 * 1024 
    
    # 1. Clean Temp Directories
    for pattern in temp_patterns:
        try:
            matches = glob.glob(pattern)
            for path in matches:
                if os.path.isdir(path):
                    shutil.rmtree(path, ignore_errors=True)
                    logger.info(f"Removed directory: {path}")
                else:
                    os.remove(path)
                    logger.info(f"Removed file: {path}")
        except Exception as e:
            logger.warning(f"Error cleaning {pattern}: {e}")
            
    # 2. Rotate/Truncate Logs
    # If running in container, stdout is captured, but if file logging is used:
    log_files = glob.glob("*.log") + glob.glob("logs/*.log")
    for log_file in log_files:
        try:
            size = os.path.getsize(log_file)
            if size > LOG_LIMIT:
                # Truncate file
                with open(log_file, "w") as f:
                    f.truncate()
                logger.info(f"Truncated oversized log: {log_file}")
        except Exception as e:
            logger.warning(f"Error checking log {log_file}: {e}")

    logger.info("Cleanup Complete.")

if __name__ == "__main__":
    cleanup_temp_resources()
