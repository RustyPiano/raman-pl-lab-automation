#ifndef __imagepro_nncam_H__
#define __imagepro_nncam_H__

#if defined(_WIN32)
#pragma pack(push, 8)
#endif

#ifdef __cplusplus
extern "C"
{
#endif

#if defined(_WIN32)
IMAGEPRO_API(HRESULT) imagepro_stitch_pull(HImageproStitch handle, HNncam h, int bFeed, void* pImageData, int bits, int rowPitch, NncamFrameInfoV2* pInfo);
IMAGEPRO_API(HRESULT) imagepro_stitch_pullV3(HImageproStitch handle, HNncam h, int bFeed, void* pImageData, int bits, int rowPitch, NncamFrameInfoV3* pInfo);

IMAGEPRO_API(HRESULT) imagepro_edf_pull(HImageproEdf handle, HNncam h, int bFeed, void* pImageData, int bits, int rowPitch, NncamFrameInfoV2* pInfo);
IMAGEPRO_API(HRESULT) imagepro_edf_pullV3(HImageproEdf handle, HNncam h, int bFeed, void* pImageData, int bits, int rowPitch, NncamFrameInfoV3* pInfo);
#endif

#ifdef __cplusplus
}
#endif

#if defined(_WIN32)
#pragma pack(pop)
#endif

#endif
