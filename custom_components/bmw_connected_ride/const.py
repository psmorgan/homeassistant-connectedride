"""Constants for the BMW Connected Ride integration."""

DOMAIN = "bmw_connected_ride"

# BMW OAuth credentials (device code flow)
BMW_CLIENT_ID = "7da8b8f8-a4f2-4789-85d4-bba0f9325889"
BMW_CLIENT_SECRET = "49dcc9ea-0782-4d2c-817e-57403895fdc4"

# GCDM OAuth base URL (both regions use this for OAuth)
GCDM_BASE_URL = "https://customer.bmwgroup.com"

# OAuth scopes
OAUTH_SCOPES = "authenticate_user openid"

# Region configuration: maps region code to data API base URL
REGION_CONFIGS = {
    "ROW": {
        "api_base_url": "https://api.connectedride.bmwgroup.com",
    },
    "NA": {
        "api_base_url": "https://api.connectedride.bmwgroup.us",
    },
}

# Refresh access token this many seconds before it actually expires
TOKEN_REFRESH_BUFFER_SECONDS = 300

# Config entry key for region selection
CONF_REGION = "region"

# Platform types to set up
PLATFORMS: list[str] = ["sensor", "device_tracker", "image"]
