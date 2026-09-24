"""Configuration for Shore IT onboarding."""

GOOGLE_DOMAIN = "shorecollaborative.org"

STAFF_WIFI_SSID = "Shore Staff"

DEVICE_MANAGEMENT = {
    "Chromebook": "Google Admin",
    "Windows": "Manual",
    "MacBook": "Mosyle",
    "iPhone": "Mosyle",
    "iPad": "Mosyle",
    "Android": None,
}

DEVICE_OPTIONS = [
    "Chromebook",
    "Windows",
    "MacBook",
    "iPhone",
    "iPad",
    "Android",
]

STANDARD_SOFTWARE = [
    "Adobe",
    "Microsoft 365",
]

SECURITY_REQUIREMENTS = [
    "Complete security awareness training",
    "Verify MFA enrollment",
]

NEEDS_REVIEW = {
    "google_groups": True,
    "sis_access": True,
    "phone_extension": True,
}