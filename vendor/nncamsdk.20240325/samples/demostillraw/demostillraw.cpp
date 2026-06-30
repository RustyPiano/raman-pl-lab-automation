#include <stdio.h>
#include <stdlib.h>
#include "nncam.h"

HNncam g_hcam = NULL;
void* g_pImageData = NULL;
unsigned g_totalVideo = 0, g_totalStill = 0;

static void SaveRaw(const char* filename, const void* pData, unsigned length)
{
    FILE* fp = fopen(filename, "wb");
    if (fp)
    {
        fwrite(pData, 1, length, fp);
        fclose(fp);
    }
}

static void __stdcall EventCallback(unsigned nEvent, void* pCallbackCtx)
{
    if (NNCAM_EVENT_IMAGE == nEvent)
    {
        NncamFrameInfoV3 info = { 0 };
        const HRESULT hr = Nncam_PullImageV3(g_hcam, g_pImageData, 0, 24, 0, &info);
        if (FAILED(hr))
            printf("failed to pull image, hr = %08x\n", hr);
        else
        {
            /* After we get the image data, we can do anything for the data we want to do */
            printf("pull image ok, total = %u, res = %u x %u\n", ++g_totalVideo, info.width, info.height);
        }
    }
    else if (NNCAM_EVENT_STILLIMAGE == nEvent)
    {
        NncamFrameInfoV3 info = { 0 };
        HRESULT hr = Nncam_PullImageV3(g_hcam, nullptr, 1, 0, 0, &info); //peek width & height
        if (FAILED(hr))
            printf("failed to pull still image, hr = %08x\n", hr);
        else
        {
            void* pStillImage = malloc(info.width * info.height); /* memory for still image */
            if (pStillImage)
            {
                /* After we get the image data, we can do anything for the data we want to do */
                hr = Nncam_PullImageV3(g_hcam, pStillImage, 1, 0, 0, &info);
                if (FAILED(hr))
                    printf("failed to pull still image, hr = %08x\n", hr);
                else
                {
                    char filename[1024];
                    g_totalStill += 1;
                    sprintf(filename, "demostillraw_%ux%u_%u.raw", info.width, info.height, g_totalStill);
                    SaveRaw(filename, pStillImage, info.width * info.height);
                    printf("pull still image ok, total = %u, res = %u x %u, save: %s\n", g_totalStill, info.width, info.height, filename);
                }

                free(pStillImage);
            }
        }
    }
    else
    {
        printf("event callback: 0x%04x\n", nEvent);
    }
}

int main(int, char**)
{
    NncamDeviceV2 arr[NNCAM_MAX] = { 0 };
    unsigned cnt = Nncam_EnumV2(arr);
    if (0 == cnt)
    {
        printf("no camera found or open failed\n");
        return -1;
    }
    for (unsigned i = 0; i < cnt; ++i)
    {
        if (arr[i].model->still > 0)
        {
#if defined(_WIN32)
            printf("%ls\n", arr[i].displayname);
#else
            printf("%s\n", arr[i].displayname);
#endif
            g_hcam = Nncam_Open(arr[i].id);
            if (NULL == g_hcam)
            {
                printf("failed to open camera\n");
                return -1;
            }
            break;
        }
    }
    if (NULL == g_hcam)
    {
        printf("no camera supports still image\n");
        return -1;
    }
    
    int nWidth = 0, nHeight = 0;
    HRESULT hr = Nncam_get_Size(g_hcam, &nWidth, &nHeight);
    if (FAILED(hr))
        printf("failed to get size, hr = %08x\n", hr);
    else
    {
        g_pImageData = malloc(TDIBWIDTHBYTES(24 * nWidth) * nHeight);
        if (NULL == g_pImageData)
            printf("failed to malloc\n");
        else
        {
            hr = Nncam_StartPullModeWithCallback(g_hcam, EventCallback, NULL);
            if (FAILED(hr))
                printf("failed to start camera, hr = %08x\n", hr);
            else
            {
                printf("press 'x' to exit, number to snap still image\n");
                do {
                    char str[1024];
                    if (fgets(str, 1023, stdin))
                    {
                        if (('x' == str[0]) || ('X' == str[0]))
                            break;
                        Nncam_SnapR(g_hcam, atoi(str), 1);
                    }
                } while (true);
            }
        }
    }
    
    /* cleanup */
    Nncam_Close(g_hcam);
    if (g_pImageData)
        free(g_pImageData);
    return 0;
}
