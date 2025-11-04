"""
Monitoring Daemon

Background service that continuously monitors parking availability
for all active monitoring jobs in the database.
"""

import sys
import time
import logging
import signal
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from config.database import get_active_monitoring_jobs
from monitoring.parking_scraper_v3 import check_monitoring_jobs

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('monitoring_daemon.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Global flag for graceful shutdown
running = True


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    global running
    logger.info("Received shutdown signal. Stopping gracefully...")
    running = False


def main():
    """
    Main daemon loop.
    Queries active jobs every 60 seconds and processes them.
    """
    global running
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    logger.info("Starting Monitoring Daemon")
    logger.info("Press Ctrl+C to stop")
    
    # Initial delay before first check (give system time to start)
    time.sleep(5)
    
    cycle_count = 0
    
    try:
        while running:
            cycle_count += 1
            logger.info(f"=== Monitoring Cycle #{cycle_count} ===")
            
            try:
                # Get active jobs count for logging
                jobs = get_active_monitoring_jobs()
                job_count = len(jobs)
                
                if job_count > 0:
                    logger.info(f"Processing {job_count} active monitoring jobs")
                    check_monitoring_jobs()
                else:
                    logger.info("No active monitoring jobs. Waiting...")
                
            except KeyboardInterrupt:
                raise
            except Exception as e:
                logger.error(f"Error in monitoring cycle: {e}", exc_info=True)
            
            # Wait before next cycle (60 seconds)
            if running:
                logger.info("Waiting 60 seconds before next cycle...")
                # Check every second if we should stop (allows responsive shutdown)
                for _ in range(60):
                    if not running:
                        break
                    time.sleep(1)
    
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        logger.info("Monitoring Daemon stopped")


if __name__ == "__main__":
    main()

