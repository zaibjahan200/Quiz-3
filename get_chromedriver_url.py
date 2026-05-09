#!/usr/bin/env python3
"""
Reads Chrome version from argv[1], queries the Chrome for Testing
JSON endpoint, and prints the linux64 ChromeDriver download URL.
"""
import sys
import json
import urllib.request

chrome_version = sys.argv[1]          # e.g. "124.0.6367.207"
chrome_major   = chrome_version.split(".")[0]

url  = "https://googlechromelabs.github.io/chrome-for-testing/known-good-versions-with-downloads.json"
with urllib.request.urlopen(url) as resp:
    data = json.load(resp)

match = None
for v in reversed(data["versions"]):
    ver = v["version"]
    downloads = v.get("downloads", {}).get("chromedriver", [])
    linux_urls = [d["url"] for d in downloads if d["platform"] == "linux64"]
    if not linux_urls:
        continue
    if ver == chrome_version:
        match = linux_urls[0]
        break
    if ver.split(".")[0] == chrome_major and match is None:
        match = linux_urls[0]

if not match:
    sys.exit(f"No ChromeDriver found for Chrome {chrome_version}")

print(match)
