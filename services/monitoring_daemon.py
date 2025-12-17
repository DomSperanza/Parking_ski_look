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
from monitoring.parking_scraper_v3 import check_monitoring_jobs
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

    # Base interval (in seconds) - increased for better stealth
    BASE_INTERVAL = 120  # 2 minutes base

    try:
        with app.app_context():
            while running:
                cycle_count += 1
                logger.info(f"=== Monitoring Cycle #{cycle_count} ===")

                try:
                    # Cleanup expired jobs
                    delete_expired_jobs()

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

                # Calculate wait time with jitter
                # Increased jitter for stealth (2-5 minutes)
                wait_time = BASE_INTERVAL + random.randint(60, 180)

                # More frequent long pauses (15% chance) to simulate user taking breaks
                if random.random() < 0.15:
                    long_pause = random.randint(600, 1200)  # 10-20 minutes
                    logger.info(
                        f"Taking a long break for {long_pause} seconds (stealth mode)..."
                    )
                    wait_time += long_pause
                
                # After every 20 cycles, take an extended break (30-60 minutes)
                if cycle_count % 20 == 0:
                    extended_break = random.randint(1800, 3600)  # 30-60 minutes
                    logger.info(
                        f"Extended cooldown after {cycle_count} cycles: {extended_break} seconds..."
                    )
                    wait_time += extended_break

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
