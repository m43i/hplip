#!/usr/bin/env python3
"""Package a native hpcups build without replacing the distribution's driver."""
import argparse
from pathlib import Path
import re
import shutil
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", default="3.26.6+horizontal2")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    binary = root / "hpcups"
    if not binary.is_file():
        parser.error("Build hpcups in the repository root first")
    architecture = subprocess.check_output(["dpkg", "--print-architecture"], text=True).strip()
    output = root / "out"
    output.mkdir(exist_ok=True)
    package = output / f"hpcups-calibrated_{args.version}_{architecture}.deb"

    with tempfile.TemporaryDirectory(prefix="hpcups-package-") as staging:
        staging = Path(staging)
        driver = staging / "usr/lib/cups/filter/hpcups-calibrated"
        driver.parent.mkdir(parents=True)
        shutil.copyfile(binary, driver)
        driver.chmod(0o755)
        subprocess.run(["strip", "--strip-unneeded", str(driver)], check=True)

        ppd = (root / "ppd/hpcups/hp-deskjet_3700_series.ppd").read_text()
        ppd = ppd.replace(' 0 hpcups"', ' 0 hpcups-calibrated"')
        ppd = re.sub(r'^\*PCFileName:.*$', '*PCFileName: "hp37cal.ppd"', ppd, flags=re.M)
        ppd += '\n*% Optional native horizontal calibration, in millimetres.\n'
        ppd += '*HPHorizontalOffset: "0"\n'
        ppd += '*HPLegacyPCL3GUI2: "1"\n'
        target = staging / "usr/share/ppd/hpcups-calibrated/hp-deskjet_3700_series.ppd"
        target.parent.mkdir(parents=True)
        target.write_text(ppd)

        helper = staging / "usr/sbin/hpcups-configure-position"
        helper.parent.mkdir(parents=True)
        shutil.copyfile(root / "tools/configure-position.py", helper)
        helper.chmod(0o755)
        docs = staging / "usr/share/doc/hpcups-calibrated"
        docs.mkdir(parents=True)
        shutil.copyfile(root / "HORIZONTAL_ALIGNMENT.md", docs / "README.md")
        shutil.copyfile(root / "COPYING", docs / "copyright")

        control = staging / "DEBIAN/control"
        control.parent.mkdir()
        control.write_text(
            f"Package: hpcups-calibrated\nVersion: {args.version}\n"
            f"Architecture: {architecture}\nSection: text\nPriority: optional\n"
            "Maintainer: Local printer administration <root@localhost>\n"
            "Depends: python3, libc6, libcups2t64, libcupsimage2t64, libjpeg62-turbo, "
            "libstdc++6, libgcc-s1, zlib1g\n"
            "Homepage: https://github.com/m43i/hplip/tree/fix/deskjet-horizontal-alignment\n"
            "Description: HPLIP raster driver with native horizontal calibration\n"
            " Optional PCL3GUI2 pixel translation without resizing the page.\n"
            " Installs separately from the distribution hpcups driver.\n"
        )
        subprocess.run(["dpkg-deb", "--root-owner-group", "--build", str(staging), str(package)], check=True)
    print(package)


if __name__ == "__main__":
    main()
