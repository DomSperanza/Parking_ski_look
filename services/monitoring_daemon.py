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
from monitoring.vpn_rotator import rotate_vpn_ip, get_current_ip
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

    # Base interval (in seconds) - aggressive checking rate
    BASE_INTERVAL = 20  # 20 seconds base

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
                    logger.warning("BLOCKED DETECTED! Attempting VPN IP rotation...")

                    # Clean up all browser sessions first
                    try:
                        cleanup_all_drivers()
                    except Exception as e:
                        logger.warning(f"Error during cleanup: {e}")

                    # Brief cooldown before rotating
                    cooldown = random.randint(30, 60)
                    logger.info(f"Waiting {cooldown}s cooldown before rotating IP...")
                    for _ in range(cooldown):
                        if not running:
                            break
                        time.sleep(1)

                    if running:
                        old_ip = get_current_ip()
                        new_ip = rotate_vpn_ip()

                        if new_ip and new_ip != old_ip:
                            logger.info(
                                f"IP rotated successfully: {old_ip} -> {new_ip}"
                            )
                            # Wait a bit more after rotation for network to stabilize
                            wait_time = random.randint(60, 90)
                            logger.info(
                                f"Waiting {wait_time}s for network to stabilize before resuming..."
                            )
                        else:
                            # Rotation failed - fall back to container restart
                            logger.error(
                                f"IP rotation failed (old={old_ip}, new={new_ip}). Restarting container..."
                            )
                            sys.exit(1)
                else:
                    # Normal operation - check with jitter
                    wait_time = BASE_INTERVAL + random.randint(5, 10)  # 25-30 seconds

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
