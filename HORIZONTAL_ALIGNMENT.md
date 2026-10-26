# Native horizontal calibration for HPLIP

This branch starts from HPLIP 3.26.6, imported by Martin Wilck from HP's
[official release](https://sourceforge.net/projects/hplip/files/hplip/3.26.6/).
It adds optional horizontal calibration to the PCL3GUI2 driver used by the
HP DeskJet 3700 family. It also makes `--disable-imageProcessor-build` stop
linking the x86-only ImageProcessor library, allowing this build on ARM64.

## Behavior

Add this printer-specific PPD attribute to request a correction:

```text
*HPHorizontalOffset: "4.2"
```

The value is millimetres. Positive moves right and negative moves left. The
valid range is -20 to +20 mm; non-finite, malformed and out-of-range values
fail the job with an error. Missing or zero means the original behavior.

The filter converts the offset to whole pixels at each page's horizontal
raster resolution, translates each row, and fills the exposed columns with
white. Pixels outside the existing printable width are clipped. It does not
resample, scale, change page dimensions, or send horizontal PCL cursor
commands. Content already clipped before reaching the driver cannot be
recovered. Calibration supports chunked 8-bit RGB and RGBW raster (including
the DeskJet PPD's grayscale modes); an incompatible format with a nonzero
pixel shift fails explicitly. Other printer languages are unchanged.

For devices that need the older RGB + separate black-plane pipeline, add:

```text
*HPLegacyPCL3GUI2: "1"
```

This disables the newer Ernie filter and restores the dual-plane PCL3GUI2
encoding used by HPLIP 3.22.10. Missing or `"0"` retains upstream 3.26.6
behavior. The packaged DeskJet 3700 PPD enables compatibility mode to keep
calibration separate from the newer upstream processing changes. Existing
JobAttributes field offsets are preserved.

Start with a measured page rather than assuming a universal offset. On the
tested device, revision 2 at +4.2 mm printed a nominal 10 mm border with
approximately 8 mm at the left and 12 mm at the right, with a 100 mm ruler
still measuring 100 mm. The next calibration therefore adds (12 - 8) / 2 =
2 mm, giving +6.2 mm total. These are per-device measurements, not a universal
default for every DeskJet 3700. The final +6.2 mm reference print was
confirmed centered by the user, with the ruler retaining its correct scale.
It does not enable borderless
printing; the printer's mechanical print limits still apply.

**Revision history:** `horizontal1` tried PCL horizontal cursor commands.
That implementation passed command-generation tests but failed the physical
printer test and was rolled back. `horizontal2` replaces it with pixel
translation and preserves the previously working black/color pipeline.
Do not install the first revision.

## Build on Raspberry Pi OS 64-bit / Debian Trixie

```sh
sudo apt-get install g++ make python3 libcups2-dev libcupsimage2-dev libjpeg-dev \
  libusb-1.0-0-dev libdbus-1-dev zlib1g-dev
./configure --enable-hpcups-only-build --disable-imageProcessor-build \
  --disable-dbus-build --disable-network-build --disable-scan-build \
  --disable-fax-build --disable-gui-build --prefix=/usr/local
make -j3 hpcups
```

The optional proprietary ImageProcessor path is disabled in this ARM build.
The existing HPLIP USB backend and scanner installation are retained.

## Regression tests without printing

```sh
python3 tests/test-horizontal-position.py --driver ./hpcups \
  --baseline /path/to/unmodified-3.26.6/hpcups \
  --legacy-baseline /usr/lib/cups/filter/hpcups \
  --ppd ppd/hpcups/hp-deskjet_3700_series.ppd
```

Both baseline arguments are optional; the legacy baseline must be HPLIP
3.22.10. Tests invoke the actual filters with CUPS raster fixtures at 300,
600 and 1200 dpi, color and grayscale, and one and two pages. The fixtures
contain pure-black pixels, color pixels, and a blank row. An independent
fixture generator places pixels at the expected translated coordinates.
The calibrated output must equal the output from filtering that pre-shifted
fixture with calibration disabled, including clipping and rounding to zero.
Compatibility mode must match the stock 3.22.10 filter's output. On the actual
A4 reference page, zero-offset compatibility output was byte-identical to
stock 3.22.10, and +4.2 mm output matched the stock driver fed a separately
translated full-page raster. Default
behavior is compared with unmodified 3.26.6; invalid values must fail.
Only timestamps and the executable's name are controlled during comparison.
No USB device or running CUPS server is required. Physical printing remains
necessary to verify a specific printer's actual margins.

## Package and configure

```sh
python3 tools/package-calibrated-hpcups.py
sudo dpkg -i out/hpcups-calibrated_3.26.6+horizontal2_arm64.deb
sudo hpcups-configure-position HP_DeskJet_3700 --offset 6.2 --paper A4
```

The package installs `hpcups-calibrated` as a separate filter and provides a
DeskJet 3700 PPD and configuration helper. It does not overwrite the
distribution's `hpcups` binary. The helper saves the queue's original PPD
under `/var/lib/hpcups-calibrated/backups/` before changing the queue.
Its custom PPD file name keeps it distinct from the stock model definition.

Print a measured page at actual size, then check both side margins and a
100 mm ruler. Also test from an AirPrint client, whose raster conversion
path differs from a direct PDF job. Recalibrate for the specific device;
do not compensate for incorrectly loaded paper or a wrong media size.

## Roll back

For the example queue, restore its saved PPD:

```sh
sudo lpadmin -p HP_DeskJet_3700 \
  -P /var/lib/hpcups-calibrated/backups/HP_DeskJet_3700.ppd
```

After the queue uses the stock driver again, the optional package can be
removed with `sudo dpkg -r hpcups-calibrated`.
