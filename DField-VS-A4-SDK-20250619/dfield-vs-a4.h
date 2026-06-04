#ifndef __DFIELD_A4_H__
#define __DFIELD_A4_H__

#ifdef __cplusplus
extern "C" {
#endif
#ifdef DFIELD_A4_EXPORTS
#define DFIELD_A4_API __declspec(dllexport)
#else
#define DFIELD_A4_API __declspec(dllimport)
#endif

	DFIELD_A4_API bool a4_open();
	DFIELD_A4_API void a4_close();

	DFIELD_A4_API bool a4_get_exposure(float * ms);
	DFIELD_A4_API bool a4_set_exposure(float ms);

	/************************************************************************/
	/* get/set Gain
	/* gain: 0-high, 1-low
	/************************************************************************/
	DFIELD_A4_API bool a4_set_gain(int gain);
	DFIELD_A4_API bool a4_get_gain(int * gain);

	/************************************************************************/
	/* Get detector or pixel size
	/************************************************************************/
	DFIELD_A4_API bool a4_get_detector_size(int * width, int * height);
	DFIELD_A4_API bool a4_get_pixel_size(float * size_um);

	/************************************************************************/
	/* get/set Read mode
	/* mode: 0-FVB, 1-IMAGE
	/************************************************************************/
	DFIELD_A4_API bool a4_set_read_mode(int mode);
	DFIELD_A4_API bool a4_get_read_mode(int * mode);

	/************************************************************************/
	/* get/set bin mode
	/* x: 1 - 64, y: 1 - 129
	/************************************************************************/
	DFIELD_A4_API bool a4_set_bin(int bin_x, int bin_y);
	DFIELD_A4_API bool a4_get_bin(int* bin_x, int* bin_y);

	/************************************************************************/
	/* get/set ROI area
	/* col_from: Begin of pixel in horizontal. [0 - width]
	/* col_to: End of pixel in horizontal [col_from - width]
	/* row_from: Begin of pixel in vertical [0 - height]
	/* row_to: End of pixel in vertical [row_from - height]
	/************************************************************************/
	DFIELD_A4_API bool a4_set_roi(int col_from, int col_to, int row_from, int row_to);
	DFIELD_A4_API bool a4_get_roi(int* col_from, int* col_to, int* row_from, int* row_to);

	/************************************************************************/
	/* Data acquisition
	/* buff: data buffer
	/* size: size of data buffer [(width / bin_x) * (height / bin_y)]
	/************************************************************************/
	DFIELD_A4_API bool a4_single_capture(long * buff, int size);

	/************************************************************************/
	/* get/set cooling temperature
	/************************************************************************/
	DFIELD_A4_API bool a4_set_cooling_temp(float temp);
	DFIELD_A4_API bool a4_get_cooling_temp(float * temp);

	/************************************************************************/
	/* Read the actual temperature of the detector
	/************************************************************************/
	DFIELD_A4_API bool a4_get_current_temp(float * temp);

	/************************************************************************/
	/* get/set Data flip
	/************************************************************************/
	DFIELD_A4_API void a4_set_flip(bool flip);
	DFIELD_A4_API void a4_get_flip(bool * flip);

#ifdef __cplusplus
}
#endif
#endif