/* Small CUPS raster fixture for exercising the real hpcups filter offline. */
#include <cups/raster.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(int argc, char **argv)
{
    cups_page_header2_t header;
    unsigned char row[256 * 4];
    unsigned int page, line, x;
    unsigned int resolution = argc > 1 ? atoi(argv[1]) : 600;
    unsigned int pages = argc > 2 ? atoi(argv[2]) : 1;
    int gray = argc > 3 && !strcmp(argv[3], "gray");
    cups_raster_t *raster = cupsRasterOpen(1, CUPS_RASTER_WRITE);
    if (!raster) return 1;
    memset(&header, 0, sizeof(header));
    strcpy(header.MediaType, "Plain");
    strcpy(header.OutputType, "0");
    strcpy(header.cupsPageSizeName, "A4");
    header.HWResolution[0] = header.HWResolution[1] = resolution;
    header.PageSize[0] = 595;
    header.PageSize[1] = 842;
    header.cupsPageSize[0] = 595.44;
    header.cupsPageSize[1] = 841.68;
    header.Margins[0] = header.Margins[1] = 8;
    header.ImagingBoundingBox[0] = header.ImagingBoundingBox[1] = 8;
    header.ImagingBoundingBox[2] = 587;
    header.ImagingBoundingBox[3] = 800;
    header.cupsImagingBBox[0] = header.cupsImagingBBox[1] = 8.4;
    header.cupsImagingBBox[2] = 587.04;
    header.cupsImagingBBox[3] = 800.64;
    header.NumCopies = 1;
    header.MediaPosition = 7;
    header.cupsInteger[0] = 26;
    header.cupsWidth = 256;
    header.cupsHeight = 8;
    header.cupsBitsPerColor = 8;
    header.cupsNumColors = gray ? 3 : 4;
    header.cupsBitsPerPixel = 8 * header.cupsNumColors;
    header.cupsBytesPerLine = header.cupsWidth * header.cupsNumColors;
    header.cupsColorOrder = CUPS_ORDER_CHUNKED;
    header.cupsColorSpace = gray ? CUPS_CSPACE_RGB : CUPS_CSPACE_RGBW;
    header.cupsRowStep = gray ? 2 : 0;
    for (page = 0; page < pages; page++) {
        if (!cupsRasterWriteHeader2(raster, &header)) return 2;
        for (line = 0; line < header.cupsHeight; line++) {
            memset(row, 255, sizeof(row));
            for (x = 32; x < 224; x++) {
                row[x * header.cupsNumColors] = 40 + line * 10;
                row[x * header.cupsNumColors + 1] = gray ? 40 + line * 10 : 100;
                row[x * header.cupsNumColors + 2] = gray ? 40 + line * 10 : 180;
            }
            if (cupsRasterWritePixels(raster, row, header.cupsBytesPerLine)
                != header.cupsBytesPerLine) return 3;
        }
    }
    cupsRasterClose(raster);
    return 0;
}
