#!/usr/bin/env python3
"""Exercise actual raster-to-PCL output; no printer or CUPS server is needed."""
import argparse
import os
from pathlib import Path
import re
import subprocess
import tempfile

START = b"\x1b*r1A"


def stable(data):
    # Job timestamps vary even when the raster and options are identical.
    return re.sub(
        rb'@PJL (?:COMMENT="Job Start Time:|SET JOBATTR="JobAcct4=|SET TIMESTAMP=)[^\r\n]*',
        b"@PJL TIMESTAMP", data,
    )


def assert_same(actual, expected, message):
    actual, expected = stable(actual), stable(expected)
    if actual != expected:
        index = next((i for i, pair in enumerate(zip(actual, expected))
                      if pair[0] != pair[1]), min(len(actual), len(expected)))
        raise AssertionError(
            f"{message} at byte {index}: "
            f"{actual[max(0, index-60):index+80]!r} != "
            f"{expected[max(0, index-60):index+80]!r}"
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--driver", type=Path, required=True)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--ppd", type=Path, required=True)
    args = parser.parse_args()
    original = args.ppd.read_text()
    with tempfile.TemporaryDirectory(prefix="hpcups-position-") as directory:
        directory = Path(directory)
        fixture = directory / "raster-fixture"
        subprocess.run([
            "cc", str(Path(__file__).with_name("position-raster.c")),
            "-lcups", "-o", str(fixture),
        ], check=True)

        def render(driver, raster, offset):
            ppd = directory / "printer.ppd"
            text = re.sub(r'^\*HPHorizontalOffset:.*\n?', '', original, flags=re.M)
            if offset is not None:
                text += f'\n*HPHorizontalOffset: "{offset}"\n'
            ppd.write_text(text)
            return subprocess.run(
                ["hpcups", "37", "test", "position-test", "1", ""],
                executable=str(driver.resolve()),
                input=raster, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                env={**os.environ, "PPD": str(ppd)}, timeout=20,
            )

        for resolution, pages, mode in [(300, 1, "color"), (600, 2, "color"),
                                        (1200, 1, "color"), (600, 1, "gray")]:
            raster = subprocess.check_output([str(fixture), str(resolution), str(pages), mode])
            zero = render(args.driver, raster, None)
            assert zero.returncode == 0, zero.stderr.decode(errors="replace")
            explicit_zero = render(args.driver, raster, "0")
            assert explicit_zero.returncode == 0
            assert_same(zero.stdout, explicit_zero.stdout, "Zero changed output")
            if args.baseline:
                baseline = render(args.baseline, raster, None)
                assert baseline.returncode == 0
                assert_same(zero.stdout, baseline.stdout, "Default output regressed")
            for offset in [4.2, -4.2]:
                result = render(args.driver, raster, str(offset))
                assert result.returncode == 0, result.stderr.decode(errors="replace")
                dots = int(abs(offset) * resolution / 25.4 + .5) * (1 if offset > 0 else -1)
                command = b"\x1b*p0X" + f"\x1b*p{dots:+d}X".encode()
                assert result.stdout.count(command + START) == pages, (
                    f"Missing per-page {offset} mm positioning at {resolution} dpi ({mode})"
                )
                unchanged = result.stdout.replace(command + START, START)
                assert_same(unchanged, zero.stdout, "Raster payload changed")
                # Form feed can retain X. Model that conservative case and
                # require the same absolute raster origin on every page.
                cursor = 0
                positions = []
                for match in re.finditer(rb'\x1b\*p([+-]?\d+)X|\x1b\*r1A', result.stdout):
                    if match.group(1) is None:
                        positions.append(cursor)
                    else:
                        value = match.group(1)
                        cursor = cursor + int(value) if value[:1] in (b'+', b'-') else int(value)
                assert positions == [dots] * pages, "Position accumulated across pages"
            for invalid in ["", " ", "nan", "inf", "21", "-21", "4.2mm", "invalid"]:
                result = render(args.driver, raster, invalid)
                assert result.returncode != 0, f"Accepted invalid offset: {invalid}"
            print(f"PASS: {resolution} dpi, {pages} page(s), {mode}: offset, payload, defaults, bounds")


if __name__ == "__main__":
    main()
