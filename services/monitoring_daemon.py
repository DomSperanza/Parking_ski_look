"""
Monitoring Daemon

Background service that continuously monitors parking availability
for all active monitoring jobs in the database.
"""

import sys
import time
import logging
import signal
import random
from pathlib import Path
from dotenv import load_dotenv

# Load env vars
load_dotenv()

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from config.database import get_active_monitoring_jobs, delete_expired_jobs
from monitoring.parking_scraper_v3 import check_monitoring_jobs, cleanup_all_drivers
from webapp.app import create_app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("monitoring_daemon.log"), logging.StreamHandler()],
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
    Queries active jobs and processes them with random jitter.
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

    # Create app for context
    app = create_app()

    # Base interval (in seconds) - balanced checking rate
    BASE_INTERVAL = 120  # 2 minutes base

    try:
        with app.app_context():
            while running:
                cycle_count += 1
                logger.info(f"=== Monitoring Cycle #{cycle_count} ===")

                was_blocked = False
                try:
                    # Cleanup expired jobs
                    delete_expired_jobs()

                    # Get active jobs count for logging
                    jobs = get_active_monitoring_jobs()
                    job_count = len(jobs)

                    if job_count > 0:
                        logger.info(f"Processing {job_count} active monitoring jobs")
                        was_blocked = check_monitoring_jobs()
                    else:
                        logger.info("No active monitoring jobs. Waiting...")

                except KeyboardInterrupt:
                    raise
                except Exception as e:
                    logger.error(f"Error in monitoring cycle: {e}", exc_info=True)

                # Calculate wait time
                if was_blocked:
                    # If blocked, wait a few minutes then restart container for fresh start
                    wait_time = random.randint(240, 360)  # 4-6 minutes
                    logger.warning(
                        f"BLOCKED DETECTED! Waiting {wait_time} seconds ({wait_time//60} minutes) then restarting container for fresh start..."
                    )
                    
                    # Wait the cooldown period
                    if running:
                        for _ in range(wait_time):
                            if not running:
                                break
                            time.sleep(1)
                    
                    # Clean up all browser sessions before restart
                    if running:
                        logger.info("Cleaning up all browser sessions before restart...")
                        try:
                            cleanup_all_drivers()
                        except Exception as e:
                            logger.warning(f"Error during cleanup: {e}")
                    
                    # Exit to trigger Docker restart (restart: always in docker-compose)
                    if running:
                        logger.info("Exiting to trigger container restart for fresh start...")
                        sys.exit(1)  # Exit with error code to ensure restart
                else:
                    # Normal operation - check with jitter
                    wait_time = BASE_INTERVAL + random.randint(10, 30)  # 120-150 seconds

                if running:
                    logger.info(f"Waiting {wait_time} seconds before next cycle...")
                    # Check every second if we should stop (allows responsive shutdown)
                    for _ in range(wait_time):
                        if not running:
                            break
                        time.sleep(1)

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        logger.info("Monitoring Daemon stopped")


if __name__ == "__main__":
    main()
