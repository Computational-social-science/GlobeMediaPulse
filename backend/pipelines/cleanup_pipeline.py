
import logging
import os
import shutil
from backend.core.config import settings
from backend.operators.storage import storage_operator

logger = logging.getLogger(__name__)

class CleanupPipeline:
    """
    Pipeline responsible for cleaning up temporary files and maintaining system hygiene.
    """
    def __init__(self):
        self.storage = storage_operator

    def run(self, dry_run=False):
        """
        Execute the cleanup process.

        Tasks:
        1. Remove temporary JSON export files from the data directory.
        2. Perform database maintenance (consistency checks or optimization).

        Args:
            dry_run (bool): If True, simulate the cleanup without actually deleting files.
        """
        logger.info("Starting Cleanup Pipeline...")
        
        # 1. File Cleanup (Logs and Temp Files)
        self._cleanup_files(dry_run)

        # 2. Database Maintenance (Pruning)
        self._prune_database(dry_run)
        
        logger.info("Cleanup Pipeline complete.")

    def _cleanup_files(self, dry_run):
        """Clean up log files and temporary data."""
        data_dir = settings.DATA_DIR
        log_dirs = [settings.BASE_DIR, os.path.join(settings.BASE_DIR, "logs")]
        
        # Files to explicitly remove
        temp_files = ["sample_news_scraped.json", "detected_errors.json"]
        
        # 1. Remove specific temp files
        for fname in temp_files:
            fpath = os.path.join(data_dir, fname)
            if os.path.exists(fpath):
                self._remove_file(fpath, dry_run)

        # 2. Rotate/Clean Logs (Generic *.log > 10MB or older than 7 days - simple impl: delete all *.log for now or just rotate?)
        # User asked for "automatic pruning logic for logs/ directory"
        # Let's delete logs older than 7 days or larger than 50MB
        MAX_SIZE = 50 * 1024 * 1024 # 50MB
        
        for d in log_dirs:
            if not os.path.exists(d): continue
            for f in os.listdir(d):
                if f.endswith(".log"):
                    fpath = os.path.join(d, f)
                    try:
                        size = os.path.getsize(fpath)
                        if size > MAX_SIZE:
                            self._remove_file(fpath, dry_run, reason="Size Limit")
                    except OSError:
                        pass

    def _remove_file(self, fpath, dry_run, reason=""):
        if dry_run:
            logger.info(f"[Dry Run] Would delete {fpath} {reason}")
        else:
            try:
                os.remove(fpath)
                logger.info(f"Deleted {fpath} {reason}")
            except OSError as e:
                logger.error(f"Failed to delete {fpath}: {e}")

    def _prune_database(self, dry_run):
        """Prune old records from database."""
        if dry_run:
            logger.info("[Dry Run] Would prune Tier-2 articles older than 12h")
        else:
            count = self.storage.prune_old_articles(retention_hours=12)
            logger.info(f"Database Pruning: Removed {count} old Tier-2 articles")

cleanup_pipeline = CleanupPipeline()
