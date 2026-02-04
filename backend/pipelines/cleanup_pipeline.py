
import logging
import os
import shutil
from backend.core.config import settings
from backend.operators.storage import storage_operator

logger = logging.getLogger(__name__)

class CleanupPipeline:
    r"""
    Pipeline for resource hygiene and storage stability.

    Research motivation: bound storage drift by enforcing a cleanup cadence that keeps
    transient artifacts within a tolerance $\Omega$ and limits log growth to $L \leq L_{\max}$.
    """
    def __init__(self):
        self.storage = storage_operator

    def run(self, dry_run=False):
        r"""
        Execute the cleanup procedure.

        Tasks:
        1. Remove transient artifacts in the data directory.
        2. Prune Tier-2 articles with a retention horizon $T=12\ \mathrm{hours}$.

        Args:
            dry_run (bool): If True, simulate deletions without mutating state.
        """
        logger.info("Starting Cleanup Pipeline...")
        self._cleanup_files(dry_run)
        self._prune_database(dry_run)
        logger.info("Cleanup Pipeline complete.")

    def _cleanup_files(self, dry_run):
        r"""
        Remove transient artifacts and oversized logs.

        A log is eligible for removal when its size exceeds $L_{\max}=50\ \mathrm{MB}$.
        """
        data_dir = settings.DATA_DIR
        log_dirs = [settings.BASE_DIR, os.path.join(settings.BASE_DIR, "logs")]
        temp_files = ["sample_news_scraped.json", "detected_errors.json"]
        for fname in temp_files:
            fpath = os.path.join(data_dir, fname)
            if os.path.exists(fpath):
                self._remove_file(fpath, dry_run)
        MAX_SIZE = 50 * 1024 * 1024
        for d in log_dirs:
            if not os.path.exists(d):
                continue
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
        """
        Remove a file path or log a dry-run action.

        Args:
            fpath (str): Relative or configured path to the target file.
            dry_run (bool): If True, log without deleting.
            reason (str): Optional reason for the deletion decision.
        """
        if dry_run:
            logger.info(f"[Dry Run] Would delete {fpath} {reason}")
        else:
            try:
                os.remove(fpath)
                logger.info(f"Deleted {fpath} {reason}")
            except OSError as e:
                logger.error(f"Failed to delete {fpath}: {e}")

    def _prune_database(self, dry_run):
        r"""
        Prune Tier-2 articles older than the retention window.

        The pruning window is $T=12\ \mathrm{hours}$, enforcing an age constraint
        $t_{\mathrm{now}}-t_i > T$ for deletion.
        """
        if dry_run:
            logger.info("[Dry Run] Would prune Tier-2 articles older than 12h")
        else:
            count = self.storage.prune_old_articles(retention_hours=12)
            logger.info(f"Database Pruning: Removed {count} old Tier-2 articles")

cleanup_pipeline = CleanupPipeline()
