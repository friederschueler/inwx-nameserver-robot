#!/usr/bin/env python3
"""
Updates INWX AAAA DNS record with the current global IPv6 address from eno1 interface.
"""

import logging
import os
import subprocess
import sys
import requests
import config

logging.basicConfig(
    level=logging.WARNING,
    format="%(levelname)s: %(message)s",
    stream=sys.stdout
)
log = logging.getLogger(__name__)

INWX_USERNAME = config.INWX_USERNAME
INWX_PASSWORD = config.INWX_PASSWORD
DOMAIN = config.DOMAIN
INTERFACE = config.INTERFACE
INWX_API_URL = config.INWX_API_URL
CACHE_FILE = getattr(config, "CACHE_FILE", "/tmp/inwx_nameserver_robot_ipv6.cache")

# Backward-compatible: allow old RECORD_NAME and new RECORD_NAMES style.
RECORD_NAMES = getattr(config, "RECORD_NAMES", [getattr(config, "RECORD_NAME", "")])
if isinstance(RECORD_NAMES, str):
    RECORD_NAMES = [RECORD_NAMES]

session = requests.Session()


def get_ipv6_address(interface):
    """Get public global IPv6 address from network interface (excludes ULA addresses)."""
    try:
        result = subprocess.run(
            ["ip", "-6", "addr", "show", interface, "scope", "global"],
            capture_output=True,
            text=True,
            check=True
        )
        
        for line in result.stdout.split('\n'):
            if 'inet6' in line and 'scope global' in line:
                # Skip deprecated addresses (old prefix still valid but no longer preferred)
                if 'deprecated' in line:
                    continue
                ipv6 = line.strip().split()[1].split('/')[0]

                # Skip ULA addresses (fc00::/7 - starts with fd or fc)
                # and link-local addresses (fe80::/10)
                if not ipv6.startswith(('fc', 'fd', 'fe80')):
                    return ipv6
        
        log.error("No public global IPv6 address found on %s", interface)
        return None
        
    except subprocess.CalledProcessError as e:
        log.error("Error getting IPv6 address: %s", e)
        return None


def inwx_api_call(method, params):
    """Make a JSON-RPC API call to INWX."""
    payload = {
        "method": method,
        "params": params
    }
    
    try:
        response = session.post(
            INWX_API_URL,
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        return response.json()
        
    except requests.RequestException as e:
        log.error("API request failed: %s", e)
        return None


def login():
    """Login to INWX API."""
    params = {
        "user": INWX_USERNAME,
        "pass": INWX_PASSWORD,
        "lang": "en"
    }
    
    result = inwx_api_call("account.login", params)
    if result and result.get("code") == 1000:
        log.debug("Login successful")
        return True
    else:
        log.error("Login failed: %s", result)
        return False


def logout():
    """Logout from INWX API."""
    inwx_api_call("account.logout", {})


def get_all_records(domain, record_type="AAAA"):
    """Get all DNS records of a specific type for a domain."""
    params = {
        "domain": domain
    }
    
    result = inwx_api_call("nameserver.info", params)
    
    if result and result.get("code") == 1000:
        records = result.get("resData", {}).get("record", [])
        return [r for r in records if r.get("type") == record_type]
    else:
        log.error("Failed to get records: %s", result)
        return []


def find_record_by_name(records, domain, record_name):
    """Find a specific record by constructing the full name."""
    if record_name:
        full_name = f"{record_name}.{domain}"
    else:
        full_name = domain
    
    for record in records:
        if record.get("name") == full_name:
            return record
    
    return None


def update_aaaa_record(record_id, ipv6_address, record_name):
    """Update AAAA record with new IPv6 address."""
    params = {
        "id": [record_id],  # Must be an array
        "content": ipv6_address
    }
    
    result = inwx_api_call("nameserver.updateRecord", params)
    
    if result and result.get("code") == 1000:
        display_name = record_name if record_name else "@"
        log.info("Updated %s -> %s", display_name, ipv6_address)
        return True
    else:
        display_name = record_name if record_name else "@"
        log.error("Failed to update %s: %s", display_name, result)
        return False


def read_cached_ipv6():
    """Read the last known IPv6 address from the cache file."""
    try:
        with open(CACHE_FILE, "r") as f:
            return f.read().strip()
    except OSError:
        return None


def write_cached_ipv6(ipv6):
    """Persist the current IPv6 address to the cache file."""
    try:
        cache_dir = os.path.dirname(CACHE_FILE)
        if cache_dir:
            os.makedirs(cache_dir, exist_ok=True)
        with open(CACHE_FILE, "w") as f:
            f.write(ipv6)
    except OSError as e:
        log.warning("Could not write cache file: %s", e)


def main():
    # Get current IPv6 address
    ipv6 = get_ipv6_address(INTERFACE)
    if not ipv6:
        sys.exit(1)

    # Skip everything if the address hasn't changed since last run
    if read_cached_ipv6() == ipv6:
        log.debug("IPv6 address unchanged (%s), skipping INWX update", ipv6)
        sys.exit(0)

    log.debug("Current public IPv6 address: %s", ipv6)

    # Login to INWX
    if not login():
        sys.exit(1)

    # Get all AAAA records for the domain
    log.debug("Fetching AAAA records for %s...", DOMAIN)
    all_records = get_all_records(DOMAIN, "AAAA")

    if not all_records:
        log.error("No AAAA records found")
        logout()
        sys.exit(1)

    # Process each record name from config
    log.debug("Processing %d record(s)...", len(RECORD_NAMES))

    updated_count = 0
    skipped_count = 0
    failed_count = 0

    for record_name in RECORD_NAMES:
        display_name = record_name if record_name else "@"
        record = find_record_by_name(all_records, DOMAIN, record_name)

        if not record:
            log.warning("Record '%s' not found", display_name)
            failed_count += 1
            continue

        record_id = record.get("id")
        current_ipv6 = record.get("content")

        log.debug("Record '%s' (ID: %s) current: %s", display_name, record_id, current_ipv6)

        if current_ipv6 == ipv6:
            log.debug("Record '%s': already up to date", display_name)
            skipped_count += 1
        else:
            log.debug("Record '%s': updating...", display_name)
            if update_aaaa_record(record_id, ipv6, display_name):
                updated_count += 1
            else:
                failed_count += 1

    # Logout
    logout()

    log.debug("Summary: updated=%d skipped=%d failed=%d", updated_count, skipped_count, failed_count)

    if failed_count > 0:
        sys.exit(1)

    # Cache the current address only after a fully successful run
    write_cached_ipv6(ipv6)


if __name__ == "__main__":
    main()
