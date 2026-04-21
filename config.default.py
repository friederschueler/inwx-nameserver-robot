"""
Configuration file for INWX IPv6 updater.
Copy this file to config.py and fill in your credentials.
"""

# INWX API credentials
INWX_USERNAME = "your_username"
INWX_PASSWORD = "your_password"

# Domain configuration
DOMAIN = "example.com"
RECORD_NAMES = [""]  # Empty string for root domain, or "www" for subdomain

# Network interface to monitor
INTERFACE = "eno1"

# API endpoint
INWX_API_URL = "https://api.domrobot.com/jsonrpc/"
