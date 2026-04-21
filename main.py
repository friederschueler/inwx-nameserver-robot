#!/usr/bin/env python3
"""
Updates INWX AAAA DNS record with the current global IPv6 address from eno1 interface.
"""

import subprocess
import sys
import requests
import config

INWX_USERNAME = config.INWX_USERNAME
INWX_PASSWORD = config.INWX_PASSWORD
DOMAIN = config.DOMAIN
INTERFACE = config.INTERFACE
INWX_API_URL = config.INWX_API_URL

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
                ipv6 = line.strip().split()[1].split('/')[0]
                
                # Skip ULA addresses (fc00::/7 - starts with fd or fc)
                # and link-local addresses (fe80::/10)
                if not ipv6.startswith(('fc', 'fd', 'fe80')):
                    return ipv6
        
        print(f"No public global IPv6 address found on {interface}")
        return None
        
    except subprocess.CalledProcessError as e:
        print(f"Error getting IPv6 address: {e}")
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
        print(f"API request failed: {e}")
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
        print("Login successful")
        return True
    else:
        print(f"Login failed: {result}")
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
        print(f"Failed to get records: {result}")
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
        print(f"✓ Successfully updated {display_name} → {ipv6_address}")
        return True
    else:
        display_name = record_name if record_name else "@"
        print(f"✗ Failed to update {display_name}: {result}")
        return False


def main():
    # Get current IPv6 address
    ipv6 = get_ipv6_address(INTERFACE)
    if not ipv6:
        sys.exit(1)
    
    print(f"Current public IPv6 address: {ipv6}\n")
    
    # Login to INWX
    if not login():
        sys.exit(1)
    
    # Get all AAAA records for the domain
    print(f"Fetching AAAA records for {DOMAIN}...")
    all_records = get_all_records(DOMAIN, "AAAA")
    
    if not all_records:
        print("No AAAA records found")
        logout()
        sys.exit(1)
    
    # Process each record name from config
    print(f"\nProcessing {len(RECORD_NAMES)} record(s)...\n")
    
    updated_count = 0
    skipped_count = 0
    failed_count = 0
    
    for record_name in RECORD_NAMES:
        display_name = record_name if record_name else "@"
        record = find_record_by_name(all_records, DOMAIN, record_name)
        
        if not record:
            print(f"✗ Record '{display_name}' not found")
            failed_count += 1
            continue
        
        record_id = record.get("id")
        current_ipv6 = record.get("content")
        
        print(f"Record '{display_name}' (ID: {record_id})")
        print(f"  Current: {current_ipv6}")
        
        if current_ipv6 == ipv6:
            print(f"  Status: Already up to date")
            skipped_count += 1
        else:
            print(f"  Status: Updating...")
            if update_aaaa_record(record_id, ipv6, display_name):
                updated_count += 1
            else:
                failed_count += 1
        
        print()
    
    # Logout
    logout()
    
    # Summary
    print("=" * 50)
    print(f"Summary:")
    print(f"  Updated: {updated_count}")
    print(f"  Skipped (already up to date): {skipped_count}")
    print(f"  Failed: {failed_count}")
    print("=" * 50)
    
    if failed_count > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
