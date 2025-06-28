#!/usr/bin/env python3
"""Simple health check script for Docker."""

import sys
import urllib.request
import urllib.error

try:
    response = urllib.request.urlopen('http://localhost:8091/health', timeout=5)
    if response.getcode() == 200:
        print("Health check passed")
        sys.exit(0)
    else:
        print(f"Health check failed with status: {response.getcode()}")
        sys.exit(1)
except Exception as e:
    print(f"Health check failed: {e}")
    sys.exit(1)