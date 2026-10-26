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
The driver resets X and emits a relative PCL cursor move before each calibrated
page's raster start, using the selected PCL units. Resetting X avoids accumulating
the offset across form feeds. It does not resample, scale or rewrite raster
data, change page dimensions, or apply the correction to other printer
languages. Existing JobAttributes field offsets are preserved.

The 4.2 mm example came from one physical A4 calibration: a nominal 10 mm
border printed with approximately 6.1 mm at the left and 14.5 mm at the right,
while the 100 mm ruler remained 100 mm. This is a per-device calibration,
not a universal default for every DeskJet 3700. It is not a borderless-printing
feature; the printer's mechanical print limits still apply.

## Build on Raspberry Pi OS 64-bit / Debian Trixie

```sh
sudo apt-get install g++ make libcups2-dev libcupsimage2-dev libjpeg-dev \
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
  --ppd ppd/hpcups/hp-deskjet_3700_series.ppd
```

To compare the zero-offset output against an unmodified 3.26.6 build, add
`--baseline /path/to/upstream/hpcups`. Tests run the actual filter with tiny
CUPS raster fixtures at 300, 600 and 1200 dpi, color and grayscale, and one
and two pages. They verify a positioning command on every page, unchanged
raster payload, default/zero equivalence, and rejection of invalid values.
Only timestamps and the executable's name are controlled during comparison.
No USB device or running CUPS server is required.

The regression suite passes on a Raspberry Pi 4 running Raspberry Pi OS
64-bit (Debian 13), including comparison against an unmodified HPLIP 3.26.6
binary built on the same Pi. The ARM build uses the normal link rule, without
a command-line override for ImageProcessor.

PCL cursor and raster-start semantics are described in HP's
[PCL 5 technical reference](https://www.hp.com/ctg/Manual/bpl13210.pdf) and
[raster graphics reference](https://www.hp.com/ctg/Manual/bpl13206.pdf).

## Package and configure

```sh
python3 tools/package-calibrated-hpcups.py
sudo dpkg -i out/hpcups-calibrated_3.26.6+horizontal1_arm64.deb
sudo hpcups-configure-position HP_DeskJet_3700 --offset 4.2 --paper A4
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
