"""
VPN IP Rotator

Uses the Gluetun control server API (http://localhost:8000) to rotate
the VPN connection when the scraper gets blocked by anti-bot protection.
Stopping and restarting the VPN causes Gluetun to connect to a new
random Mullvad server, giving us a fresh IP address.
"""

import time
import logging
import requests

logger = logging.getLogger(__name__)

GLUETUN_API = "http://localhost:8000"
VPN_STATUS_URL = f"{GLUETUN_API}/v1/vpn/status"
PUBLIC_IP_URL = f"{GLUETUN_API}/v1/publicip/ip"

# Timeouts for API calls (short since it's localhost)
API_TIMEOUT = 10


def get_current_ip():
    """
    Get the current public IP from the Gluetun API.
    Returns the IP string or None on failure.
    """
    try:
        resp = requests.get(PUBLIC_IP_URL, timeout=API_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        return data.get("public_ip")
    except Exception as e:
        logger.warning(f"Could not get current IP from Gluetun: {e}")
        return None


def get_vpn_status():
    """
    Get the current VPN status from the Gluetun API.
    Returns 'running', 'stopped', or None on failure.
    """
    try:
        resp = requests.get(VPN_STATUS_URL, timeout=API_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        return data.get("status")
    except Exception as e:
        logger.warning(f"Could not get VPN status: {e}")
        return None


def _set_vpn_status(status):
    """
    Set VPN status to 'running' or 'stopped'.
    Returns True on success, False on failure.
    """
    try:
        resp = requests.put(
            VPN_STATUS_URL,
            json={"status": status},
            timeout=API_TIMEOUT,
        )
        resp.raise_for_status()
        logger.info(f"VPN status set to: {status}")
        return True
    except Exception as e:
        logger.error(f"Failed to set VPN status to {status}: {e}")
        return False


def wait_for_vpn_ready(timeout=60):
    """
    Wait for the VPN to reach 'running' status.
    Returns True if VPN is ready, False if timeout reached.
    """
    start = time.time()
    while time.time() - start < timeout:
        status = get_vpn_status()
        if status == "running":
            return True
        time.sleep(3)
    logger.error(f"VPN did not become ready within {timeout}s")
    return False


def rotate_vpn_ip(max_attempts=3):
    """
    Rotate the VPN IP by stopping and restarting the VPN connection.
    Gluetun will connect to a new random server on restart.

    Args:
        max_attempts: Number of times to try rotating if we get the same IP

    Returns:
        The new IP address string, or None on failure.
    """
    old_ip = get_current_ip()
    logger.info(f"Starting VPN IP rotation (current IP: {old_ip})")

    for attempt in range(max_attempts):
        logger.info(f"Rotation attempt {attempt + 1}/{max_attempts}")

        # Step 1: Stop VPN
        if not _set_vpn_status("stopped"):
            logger.error("Failed to stop VPN, aborting rotation")
            return None

        # Wait for VPN to fully stop
        time.sleep(5)

        # Step 2: Start VPN (will connect to a new random server)
        if not _set_vpn_status("running"):
            logger.error("Failed to start VPN, aborting rotation")
            return None

        # Step 3: Wait for VPN to be ready
        if not wait_for_vpn_ready(timeout=60):
            logger.error("VPN did not reconnect after rotation")
            return None

        # Extra wait for network to stabilize
        time.sleep(5)

        # Step 4: Check new IP
        new_ip = get_current_ip()
        if new_ip and new_ip != old_ip:
            logger.info(f"VPN IP rotated successfully: {old_ip} -> {new_ip}")
            return new_ip
        elif new_ip == old_ip:
            logger.warning(f"Got same IP after rotation ({new_ip}), trying again...")
            continue
        else:
            logger.warning("Could not verify new IP, but VPN is running")
            return None

    logger.error(f"Failed to get a new IP after {max_attempts} attempts")
    # VPN should still be running, return whatever IP we have
    return get_current_ip()
