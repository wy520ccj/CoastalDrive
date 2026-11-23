/* BC6H格式转换入口；bcdec使用MIT许可，原件仅由本地准备工具读取。 */
#define BCDEC_IMPLEMENTATION
#include "../third_party/bcdec/bcdec.h"

__declspec(dllexport) int decode_bc6h_hdr(const unsigned char* source,
    unsigned int bytes, float* dest, int width, int height) {
    if (width < 4 || height < 4 || width % 4 || height % 4 ||
        bytes != (unsigned int)(width / 4 * (height / 4) * 16)) return -1;
    for (int y = 0; y < height / 4; y++)
        for (int x = 0; x < width / 4; x++)
            bcdec_bc6h_float(source + (y * (width / 4) + x) * 16,
                dest + (y * 4 * width + x * 4) * 3, width * 3, 0);
    return 0;
}
