#ifndef __nncam_labview_h__
#define __nncam_labview_h__

#include "extcode.h"

#ifdef NNCAM_LABVIEW_EXPORTS
#define NNCAM_LABVIEW_API(x) __declspec(dllexport)    x   __cdecl
#else
#define NNCAM_LABVIEW_API(x) __declspec(dllimport)    x   __cdecl
#include "nncam.h"
#endif

#ifdef __cplusplus
extern "C" {
#endif

NNCAM_LABVIEW_API(HRESULT) Start(HNncam h, LVUserEventRef* rwer);

#ifdef __cplusplus
}
#endif

#endif