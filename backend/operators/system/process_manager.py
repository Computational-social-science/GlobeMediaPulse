
import subprocess
import logging
import os
import sys
import threading
import time
from collections import deque
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
        self._crawler_stdout_tail = deque(maxlen=200)
        self._crawler_stderr_tail = deque(maxlen=200)
        self._crawler_last_exit_code: Optional[int] = None
        self._crawler_last_exit_at: Optional[float] = None
        self._crawler_last_spawn_error: Optional[str] = None
        self._initialized = True
        logger.info("ProcessManager initialized.")

    def get_crawler_alerts(self) -> dict:
        stderr_lines = list(self._crawler_stderr_tail)
        stdout_lines = list(self._crawler_stdout_tail)
        combined = stderr_lines + stdout_lines

        def _count_substrings(lines, needles):
            c = 0
            for line in lines:
                for n in needles:
                    if n in line:
                        c += 1
                        break
            return c

        has_traceback = any("Traceback (most recent call last)" in line for line in stderr_lines)
        rate_limit_hits = _count_substrings(combined, ["Rate Limited (429)", " 429 "])
        forbidden_hits = _count_substrings(combined, ["Access Forbidden (403)", " 403 "])
        network_error_hits = _count_substrings(
            combined,
            [
                "DNSLookupError",
                "TCPTimedOutError",
                "TimeoutError",
                "ResponseNeverReceived",
                "ConnectionLost",
                "ConnectionRefusedError",
            ],
        )

        return {
            "has_traceback": has_traceback,
            "rate_limit_hits": rate_limit_hits,
            "forbidden_hits": forbidden_hits,
            "network_error_hits": network_error_hits,
        }

    def start_crawler(self):
        """Starts the Scrapy crawler process."""
        if self.is_crawler_running():
            logger.warning("Crawler process is already running.")
            return

        try:
            project_root = os.getcwd()
            crawlers_root = os.path.join(project_root, "backend", "crawlers")
            env = os.environ.copy()
            env["PYTHONPATH"] = f"{project_root}{os.pathsep}{crawlers_root}"
            env["SCRAPY_SETTINGS_MODULE"] = "news_crawlers.settings"

            # Command: scrapy crawl universal_news
            # Note: We use 'scrapy' from the same environment as the python interpreter
            # python -m scrapy crawl ...
            cmd = [sys.executable, '-m', 'scrapy', 'crawl', 'universal_news']
            
            logger.info(f"Starting Crawler Process: {' '.join(cmd)}")
            
            self.crawler_process = subprocess.Popen(
                cmd,
                cwd=crawlers_root,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, # We might want to capture this for the log viewer
                text=True,
                bufsize=1, # Line buffered
                encoding='utf-8', # Ensure utf-8 decoding
                errors='replace' # Handle encoding errors gracefully (e.g. non-utf8 system warnings)
            )
            self.crawler_start_time = time.time()
            self._crawler_last_spawn_error = None
            thread_status.heartbeat('crawler')
            logger.info(f"Crawler started with PID: {self.crawler_process.pid}")
            
            # Start threads to read stdout/stderr and log it to the main logger
            # This ensures logs are picked up by the WebSocketLogHandler and sent to frontend
            self._start_log_reader(self.crawler_process.stdout, logging.INFO, "ScrapyOut")
            self._start_log_reader(self.crawler_process.stderr, logging.ERROR, "ScrapyErr")
            
        except Exception as e:
            self._crawler_last_spawn_error = f"{type(e).__name__}: {e}"
            logger.error(f"Failed to start crawler: {e}")

    def _start_log_reader(self, pipe, level, logger_name_suffix):
        """Starts a daemon thread to read from a pipe and log lines."""
        def read_pipe():
            with pipe:
                for line in iter(pipe.readline, ''):
                    if line:
                        clean_line = line.strip()
                        if clean_line:
                            if logger_name_suffix == "ScrapyErr":
                                self._crawler_stderr_tail.append(clean_line)
                            else:
                                self._crawler_stdout_tail.append(clean_line)
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
            self._crawler_last_exit_code = int(poll)
            self._crawler_last_exit_at = time.time()
            return False

    def get_crawler_diagnostics(self) -> dict:
        proc = self.crawler_process
        running = self.is_crawler_running()
        pid = None
        try:
            pid = int(proc.pid) if proc else None
        except Exception:
            pid = None
        uptime_s = None
        if running and self.crawler_start_time:
            uptime_s = max(0.0, time.time() - float(self.crawler_start_time))
        return {
            "running": running,
            "pid": pid,
            "uptime_s": uptime_s,
            "last_exit_code": self._crawler_last_exit_code,
            "last_exit_at": self._crawler_last_exit_at,
            "last_spawn_error": self._crawler_last_spawn_error,
            "alerts": self.get_crawler_alerts(),
            "stderr_tail": list(self._crawler_stderr_tail),
            "stdout_tail": list(self._crawler_stdout_tail),
        }

process_manager = ProcessManager()
