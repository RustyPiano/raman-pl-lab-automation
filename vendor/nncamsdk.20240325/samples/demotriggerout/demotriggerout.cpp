#include <stdio.h>
#include <stdlib.h>
#include "nncam.h"

HNncam g_hcam = NULL;
void* g_pImageData = NULL;
unsigned g_total = 0;

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
            printf("pull image ok, total = %u, res = %u x %u\n", ++g_total, info.width, info.height);
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
        printf("press ENTER to exit\n");
        getc(stdin);
        return -1;
    }
    for (unsigned i = 0; i < cnt; ++i)
    {
        if (arr[i].model->flag & NNCAM_FLAG_TRIGGER_EXTERNAL)
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
                printf("press ENTER to exit\n");
                getc(stdin);
                return -1;
            }
            break;
        }
    }
    if (NULL == g_hcam)
    {
        printf("no camera supports external trigger\n");
        printf("press ENTER to exit\n");
        getc(stdin);
        return -1;
    }

    int nWidth = 0, nHeight = 0, trigger_source = -1, external_source = -1, outputMode = -1;
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
            Nncam_put_ExpoTime(g_hcam, 250000);
            hr = Nncam_put_Option(g_hcam, NNCAM_OPTION_TRIGGER, 2);
            if (FAILED(hr))
                printf("failed to set external trigger mode, hr = %08x\n", hr);
            else
            {
                char str[1024];
                printf("select trigger source:\n0-> Opto-isolated input\n1-> Software\n");
                do {
                    if (fgets(str, 1023, stdin))
                    {
                        switch (str[0])
                        {
                        case '0': trigger_source = 0; break;
                        case '1': trigger_source = 5; break;
                        default: trigger_source = -1; break;
                        }
                        if (-1 == trigger_source)
                            printf("bad input\n");
                        else
                        {
                            Nncam_IoControl(g_hcam, 0, NNCAM_IOCONTROLTYPE_SET_TRIGGERSOURCE, trigger_source, NULL);//select trigger source
                            Nncam_IoControl(g_hcam, 2, NNCAM_IOCONTROLTYPE_SET_GPIODIR, 0x01, NULL);//GPIO_0 -> output
                            Nncam_IoControl(g_hcam, 3, NNCAM_IOCONTROLTYPE_SET_GPIODIR, 0x01, NULL);//GPIO_1 -> output
                            Nncam_IoControl(g_hcam, 1, NNCAM_IOCONTROLTYPE_SET_OUTPUTMODE, 0x00, NULL);//opt_out -> Trigger wait signal
                            Nncam_IoControl(g_hcam, 2, NNCAM_IOCONTROLTYPE_SET_OUTPUTMODE, 0x01, NULL);//GPIO_0 -> Exposure effective signal
                            Nncam_IoControl(g_hcam, 3, NNCAM_IOCONTROLTYPE_SET_OUTPUTMODE, 0x02, NULL);//GPIO_1 -> Strobe signal
                            Nncam_IoControl(g_hcam, 3, NNCAM_IOCONTROLTYPE_SET_STROBEDELAYMODE, 0x01, NULL);//strobe delay mode
                            Nncam_IoControl(g_hcam, 3, NNCAM_IOCONTROLTYPE_SET_STROBEDELAYTIME, 500000, NULL);//strobe delay time
                            break;
                        }
                    }
                } while (true);

                hr = Nncam_StartPullModeWithCallback(g_hcam, EventCallback, NULL);
                if (FAILED(hr))
                    printf("failed to start camera, hr = %08x\n", hr);
                else
                {
                    if (5 == trigger_source)
                        printf("'x' to exit, number to trigger\n");
                    else
                        printf("'x' to exit\n");
                    do {
                        if (fgets(str, 1023, stdin))
                        {
                            if (('x' == str[0]) || ('X' == str[1]))
                                break;
                            if (5 == trigger_source)
                            {
                                int n = atoi(str);
                                if (n > 0)
                                    Nncam_Trigger(g_hcam, n);
                            }
                        }
                    } while (true);
                }
            }
        }
    }

    printf("press ENTER to exit\n");
    getc(stdin);

    /* cleanup */
    Nncam_Close(g_hcam);
    if (g_pImageData)
        free(g_pImageData);
    return 0;
}
