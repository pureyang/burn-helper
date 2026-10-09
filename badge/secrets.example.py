# Copy to badge/secrets.py (git-ignored) and fill in. tools/deploy.py installs it
# as /system/secrets.py on the badge.
WIFI_SSID = ""
WIFI_PASSWORD = ""
# More networks to try in order, e.g. your phone's hotspot:
WIFI_EXTRA = [
    # ("My iPhone", "hotspot-password"),
]
# Leave blank to find the bridge automatically (UDP beacon on the LAN).
BRIDGE = ""
REGION = "us"  # Options are us, cuba, eu, moldova, lebanon, egypt, chile, australia, nz
TIMEZONE = -8  # Standard-time offset from GMT in hours; REGION applies daylight saving
