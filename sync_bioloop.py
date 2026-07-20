#!/usr/bin/env python3

import subprocess
from pathlib import Path

PI_HOST = "hhobbs@BioLoop"
REMOTE_DIR = "~/BioLoop/data/experiments/"
LOCAL_DIR = str(Path.home() / "BioLoop_Backups")

Path(LOCAL_DIR).mkdir(parents=True, exist_ok=True)

cmd = [
    "rsync",
    "-avz",
    "--progress",
    f"{PI_HOST}:{REMOTE_DIR}",
    LOCAL_DIR,
]

print("Syncing BioLoop data...")

result = subprocess.run(cmd)

if result.returncode == 0:
    print("\n✓ Backup complete")
else:
    print("\n✗ Backup failed")