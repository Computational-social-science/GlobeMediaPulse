
import subprocess
import logging
import os
import sys
import threading
import time
from typing import Optional
from backend.core.monitoring import thread_status

logger = logging.getLogger(__name__)

class ProcessManager:
    """
    Singleton manager for external subprocesses (e.g., Scrapy Crawlers).
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(ProcessManager, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        
        self.crawler_process: Optional[subprocess.Popen] = None
        self.crawler_start_time = 0
        self._initialized = True
        logger.info("ProcessManager initialized.")

    def start_crawler(self):
        """Starts the Scrapy crawler process."""
        if self.is_crawler_running():
            logger.warning("Crawler process is already running.")
            return

        try:
            # Path to the directory containing scrapy.cfg or the module root
            # Assuming backend/crawlers/news_crawlers is the Scrapy project root
            cwd = os.path.join(os.getcwd(), 'backend', 'crawlers', 'news_crawlers')
            
            # If scrapy.cfg is not there, we might need to set PYTHONPATH
            env = os.environ.copy()
            # Add project root and backend/crawlers to PYTHONPATH
            # Project root: for 'backend' imports
            # backend/crawlers: for 'news_crawlers' imports (as Scrapy expects modules to be importable)
            crawlers_path = os.path.join(os.getcwd(), 'backend', 'crawlers')
            env['PYTHONPATH'] = f"{os.getcwd()}{os.pathsep}{crawlers_path}"
            env['SCRAPY_SETTINGS_MODULE'] = 'backend.crawlers.news_crawlers.settings'

            # Command: scrapy crawl universal_news
            # Note: We use 'scrapy' from the same environment as the python interpreter
            # python -m scrapy crawl ...
            cmd = [sys.executable, '-m', 'scrapy', 'crawl', 'universal_news']
            
            logger.info(f"Starting Crawler Process: {' '.join(cmd)}")
            
            self.crawler_process = subprocess.Popen(
                cmd,
                cwd=os.getcwd(), # Run from project root so python path works for imports
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, # We might want to capture this for the log viewer
                text=True,
                bufsize=1, # Line buffered
                encoding='utf-8', # Ensure utf-8 decoding
                errors='replace' # Handle encoding errors gracefully (e.g. non-utf8 system warnings)
            )
            self.crawler_start_time = time.time()
            thread_status.heartbeat('crawler')
            logger.info(f"Crawler started with PID: {self.crawler_process.pid}")
            
            # Start threads to read stdout/stderr and log it to the main logger
            # This ensures logs are picked up by the WebSocketLogHandler and sent to frontend
            self._start_log_reader(self.crawler_process.stdout, logging.INFO, "ScrapyOut")
            self._start_log_reader(self.crawler_process.stderr, logging.ERROR, "ScrapyErr")
            
        except Exception as e:
            logger.error(f"Failed to start crawler: {e}")

    def _start_log_reader(self, pipe, level, logger_name_suffix):
        """Starts a daemon thread to read from a pipe and log lines."""
        def read_pipe():
            with pipe:
                for line in iter(pipe.readline, ''):
                    if line:
                        clean_line = line.strip()
                        if clean_line:
                            # Log with a specific name so we know it's from the crawler
                            l = logging.getLogger(f"crawler.{logger_name_suffix}")
                            l.log(level, clean_line)
        
        t = threading.Thread(target=read_pipe, daemon=True)
        t.start()

    def stop_crawler(self):
        """Stops the crawler process."""
        if self.crawler_process:
            logger.info(f"Stopping crawler PID: {self.crawler_process.pid}")
            self.crawler_process.terminate()
            try:
                self.crawler_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.crawler_process.kill()
            self.crawler_process = None
            logger.info("Crawler stopped.")

    def restart_crawler(self):
        """Restarts the crawler."""
        self.stop_crawler()
        time.sleep(1)
        self.start_crawler()

    def is_crawler_running(self) -> bool:
        """Checks if the crawler process is alive."""
        if self.crawler_process is None:
            return False
        
        poll = self.crawler_process.poll()
        if poll is None:
            thread_status.heartbeat('crawler') # Update heartbeat if alive
            return True
        else:
            return False

process_manager = ProcessManager()
