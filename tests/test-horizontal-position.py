#!/usr/bin/env python3
"""Exercise actual raster-to-PCL output; no printer or CUPS server is needed."""
import argparse
import os
from pathlib import Path
import re
import subprocess
import tempfile


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
    parser.add_argument("--legacy-baseline", type=Path, help="Unmodified 3.22.10 filter")
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

        def render(driver, raster, offset, legacy=None):
            ppd = directory / "printer.ppd"
            text = re.sub(r'^\*(?:HPHorizontalOffset|HPLegacyPCL3GUI2):.*\n?', '', original, flags=re.M)
            if offset is not None:
                text += f'\n*HPHorizontalOffset: "{offset}"\n'
            if legacy is not None:
                text += f'\n*HPLegacyPCL3GUI2: "{legacy}"\n'
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
            for legacy in [None, "1"]:
                reference_driver = args.driver
                if legacy == "1" and args.legacy_baseline:
                    reference_driver = args.legacy_baseline
                legacy_zero = render(args.driver, raster, None, legacy)
                reference_zero = render(reference_driver, raster, None, legacy)
                assert legacy_zero.returncode == reference_zero.returncode == 0
                assert_same(legacy_zero.stdout, reference_zero.stdout, "Legacy pipeline regressed")
                for offset in [4.2, -4.2, 6.2, .001, 20, -20]:
                    dots = int(abs(offset) * resolution / 25.4 + .5) * (1 if offset > 0 else -1)
                    shifted = subprocess.check_output([
                        str(fixture), str(resolution), str(pages), mode, str(dots),
                    ])
                    result = render(args.driver, raster, str(offset), legacy)
                    reference = render(reference_driver, shifted, None, legacy)
                    assert result.returncode == reference.returncode == 0
                    assert_same(result.stdout, reference.stdout,
                                f"Pixel translation failed: {offset} mm, {resolution} dpi, {mode}, legacy={legacy}")
            legacy_disabled = render(args.driver, raster, None, "0")
            assert legacy_disabled.returncode == 0
            assert_same(legacy_disabled.stdout, zero.stdout, "Disabled legacy mode changed output")
            for invalid in ["2", "-1", "yes", ""]:
                result = render(args.driver, raster, None, invalid)
                assert result.returncode != 0, f"Accepted invalid compatibility flag: {invalid}"
            for invalid in ["", " ", "nan", "inf", "21", "-21", "4.2mm", "invalid"]:
                result = render(args.driver, raster, invalid)
                assert result.returncode != 0, f"Accepted invalid offset: {invalid}"
            print(f"PASS: {resolution} dpi, {pages} page(s), {mode}: pixel translation, legacy pipeline, defaults, clipping, bounds")

        unsupported = subprocess.check_output([str(fixture), "600", "1", "cmyk"])
        result = render(args.driver, unsupported, "4.2")
        assert result.returncode != 0, "Accepted unsupported CMYK calibration"
        assert b"requires chunked 8-bit RGB or RGBW" in result.stderr
        print("PASS: unsupported calibration format fails explicitly")


if __name__ == "__main__":
    main()
