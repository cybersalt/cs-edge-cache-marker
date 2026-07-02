"""Build the CS Edge Cache Marker install zip with forward-slash entries.

7-Zip on Windows uses backslashes internally which some Joomla installers
mangle. This script uses Python's zipfile module which produces spec-clean
forward-slash entries on any OS.
"""
import os
import shutil
import sys
import zipfile
from datetime import datetime

VERSION = "1.0.1"
SRC = r"E:\github\cs-edge-cache-marker\plg_system_csedgecachemarker"
# Per Joomla-Brain PACKAGE-BUILD-NOTES §"Package Output Location":
# built zips live in the repo root, not in dist/.
DST_DIR = r"E:\github\cs-edge-cache-marker"

ts = datetime.now().strftime("%Y%m%d_%H%M")
timestamped_name = f"plg_system_csedgecachemarker_v{VERSION}_{ts}.zip"
clean_name       = f"plg_system_csedgecachemarker_v{VERSION}.zip"
timestamped_dst  = os.path.join(DST_DIR, timestamped_name)
clean_dst        = os.path.join(DST_DIR, clean_name)

with zipfile.ZipFile(timestamped_dst, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    for root, dirs, files in os.walk(SRC):
        for f in files:
            full = os.path.join(root, f)
            rel = os.path.relpath(full, SRC).replace(os.sep, "/")
            z.write(full, rel)
            print("added:", rel)

# Per VERSION-BUMP-CHECKLIST: build script produces the timestamped iteration
# artifact; then copy to the clean version-only name that goes on the release.
shutil.copyfile(timestamped_dst, clean_dst)

print("Wrote:", timestamped_dst)
print("Wrote:", clean_dst)
print("Size:", os.path.getsize(clean_dst), "bytes")
