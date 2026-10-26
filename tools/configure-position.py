#!/usr/bin/env python3
"""Assign the calibrated DeskJet driver to an existing CUPS queue, with a backup."""
import argparse
import math
from pathlib import Path
import re
import shutil
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("queue")
    parser.add_argument("--offset", type=float, required=True, help="Millimetres; positive moves right")
    parser.add_argument("--paper", default="A4")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.queue):
        parser.error("Use a queue name containing letters, digits, underscores or hyphens")
    if not math.isfinite(args.offset) or not -20 <= args.offset <= 20:
        parser.error("Offset must be a finite number from -20 to 20 mm")

    current = Path("/etc/cups/ppd") / f"{args.queue}.ppd"
    template = Path("/usr/share/ppd/hpcups-calibrated/hp-deskjet_3700_series.ppd")
    original = current.read_text()
    ppd = template.read_text().replace('*HPHorizontalOffset: "0"', f'*HPHorizontalOffset: "{args.offset:g}"')
    backup = Path("/var/lib/hpcups-calibrated/backups") / current.name
    if not backup.exists():
        if "hpcups-calibrated" in original:
            parser.error("The original driver backup is missing; refusing to replace it")
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(current, backup)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".ppd") as file:
        file.write(ppd)
        file.flush()
        subprocess.run([
            "lpadmin", "-p", args.queue, "-P", file.name, "-o", f"PageSize={args.paper}",
        ], check=True)
    print(f"{args.queue}: horizontal offset {args.offset:+g} mm; backup: {backup}")


if __name__ == "__main__":
    main()
