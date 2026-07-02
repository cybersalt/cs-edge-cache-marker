"""Build the CS Edge Cache Marker install zip with forward-slash entries.

7-Zip on Windows uses backslashes internally which some Joomla installers
mangle. This script uses Python's zipfile module which produces spec-clean
forward-slash entries on any OS.
"""
import os
import sys
import zipfile
from datetime import datetime

VERSION = "1.0.0"
SRC = r"E:\github\cs-edge-cache-marker\plg_system_csedgecachemarker"
DST_DIR = r"E:\github\cs-edge-cache-marker\dist"

ts = datetime.now().strftime("%Y%m%d_%H%M")
name = f"plg_system_csedgecachemarker_v{VERSION}_{ts}.zip"
dst = os.path.join(DST_DIR, name)

with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    for root, dirs, files in os.walk(SRC):
        for f in files:
            full = os.path.join(root, f)
            rel = os.path.relpath(full, SRC).replace(os.sep, "/")
            z.write(full, rel)
            print("added:", rel)

print("Wrote:", dst)
print("Size:", os.path.getsize(dst), "bytes")
