#ifndef _SPECTROMETER_H_
#define _SPECTROMETER_H_

//Macro definition - Peripherals
#define PERIPHERAL_FILTER_OUTSIDE			0x0001		//Filter
#define PERIPHERAL_EXPORT							0x0002		//Export mirror
#define PERIPHERAL_SLIT_SIDE_IN					0x0004		//Slit - Side in
#define PERIPHERAL_SLIT_SIDE_OUT				0x0008		//Slit - Side out
#define PERIPHERAL_SLIT_FRONT_OUT			0x0010		//Slit - Front out
#define PERIPHERAL_SLIT_FRONT_IN				0x0020		//Slit - Front in
#define PERIPHERAL_ENTRANCE					0x0040		//Entrance mirror
#define PERIPHERAL_FILTER_INSIDE				0x0080		//Filter Inside - omni320s
#define PERIPHERAL_SHUTTER1						0x0100		//Shutter 1
#define PERIPHERAL_SHUTTER2						0x0200		//Shutter 2
#define PERIPHERAL_FOCUS_MIRROR			0x0400		//Focus mirror, C-T model only
#define PERIPHERAL_RESERVE						0x0800		//Reserve, C-T model only
#define PERIPHERAL_DIAPHRAGM_SIDE		0x1000		//Side entrance diaphragm, C-T model only
#define PERIPHERAL_DIAPHRAGM_FRONT	0x2000		//Front entrance diaphragm, C-T model only
//Macro definition - Motors
#define MOTOR_FILTER_OUTSIDE					0x0002
#define MOTOR_EXPORT								0x0003
#define MOTOR_SLIT_SIDE_IN						0x0004
#define MOTOR_SLIT_SIDE_OUT					0x0005
#define MOTOR_SLIT_FRONT_OUT				0x0006
#define MOTOR_SLIT_FRONT_IN					0x0007
#define MOTOR_ENTRANCE							0x0008
#define MOTOR_FILTER_INSIDE						0x0009
#define MOTOR_FOCUS_MIRROR					0x000A
#define MOTOR_RESERVE								0x000B
#define MOTOR_DIAPHRAGM_SIDE				0x000C
#define MOTOR_DIAPHRAGM_FRONT			0x000D
//data types
typedef struct _SPEC_INFO_
{
	char manufacturer[9];
	char model[24];
	char sn[24];
	char date[9];
	char firmware_ver[9]; //Read Only
}spec_info;

#ifdef __cplusplus
extern "C" {
#endif
#ifdef SPECTROMETER_EXPORTS
#define SPECTROMETER_API __declspec(dllexport)
#else
#define SPECTROMETER_API __declspec(dllimport)
#endif
	//////////////////////////////////////////////////////////////////////////
	SPECTROMETER_API	void	spec_get_dll_ver(char* buff, int len);

	SPECTROMETER_API	void	spec_set_usb_mode(bool usb);

	SPECTROMETER_API	int	spec_enum_dev_count();
	SPECTROMETER_API	bool	spec_enum_dev_sn(int index, char* buff, int len);

	SPECTROMETER_API	int	spec_open(const char* info);
	SPECTROMETER_API	bool	spec_close(int id);

	SPECTROMETER_API	bool	spec_get_is_open(int id);

	SPECTROMETER_API	void	spec_get_error(int id, char* buff, int len);

	//////////////////////////////////////////////////////////////////////////
	SPECTROMETER_API	bool	spec_set_timeout(int id, int ms_read, int ms_write);

	SPECTROMETER_API	bool	spec_set_dev_info(int id, spec_info info);
	SPECTROMETER_API	bool	spec_get_dev_info(int id, spec_info* ptr);

	SPECTROMETER_API	bool	spec_backup(int id);
	SPECTROMETER_API	bool	spec_restore(int id);

	SPECTROMETER_API	bool	spec_set_total_steps(int id, long steps);
	SPECTROMETER_API	bool	spec_get_total_steps(int id, long* steps);

	SPECTROMETER_API	bool	spec_set_io_output(int id, short val);
	SPECTROMETER_API	bool	spec_get_io_output(int id, short* ptr);

	SPECTROMETER_API	bool	spec_set_turret(int id, int num);
	SPECTROMETER_API	bool	spec_get_turret(int id, int* num);

	SPECTROMETER_API	bool	spec_set_zero_offset(int id, int grating, long step);
	SPECTROMETER_API	bool	spec_get_zero_offset(int id, int grating, long* step);

	SPECTROMETER_API	bool	spec_set_zero_pos(int id, int grating, int mirror, long step);
	SPECTROMETER_API	bool	spec_get_zero_pos(int id, int grating, int mirror, long* step);

	SPECTROMETER_API	bool	spec_set_adjustment(int id, int grating, float val);
	SPECTROMETER_API	bool	spec_get_adjustment(int id, int grating, float* val);

	SPECTROMETER_API	bool	spec_get_max_wavelength(int id, int grating, float* val);

	SPECTROMETER_API	bool	spec_adjusting(int id, int grating, float wave_set, float wave_real, float* result);

	SPECTROMETER_API	bool	spec_set_grating_info(int id, int grating, int groove, long blaze);
	SPECTROMETER_API	bool	spec_get_grating_info(int id, int grating, int* groove, long* blaze);

	SPECTROMETER_API	bool	spec_set_init_grating(int id, int grating);
	SPECTROMETER_API	bool	spec_get_init_grating(int id, int* grating);

	SPECTROMETER_API	bool	spec_set_init_wave(int id, int grating, float wave);
	SPECTROMETER_API	bool	spec_get_init_wave(int id, int grating, float* wave);

	SPECTROMETER_API	bool	spec_set_dispersion(int id, float val);
	SPECTROMETER_API	bool	spec_get_dispersion(int id, float* val);

	SPECTROMETER_API	bool	spec_set_grating_home(int id);

	SPECTROMETER_API	bool	spec_get_grating_count(int id, short * count);

	SPECTROMETER_API	bool	spec_set_grating(int id, int grating);
	SPECTROMETER_API	bool	spec_get_grating(int id, int* grating);

	SPECTROMETER_API	bool	spec_move_wave(int id, float wave);

	SPECTROMETER_API	bool	spec_move_to_wave(int id, float wave);

	SPECTROMETER_API	bool	spec_get_curr_steps(int id, float* steps);

	SPECTROMETER_API	bool	spec_move_steps(int id, float steps);
	SPECTROMETER_API	bool	spec_move_to_steps(int id, float steps);

	SPECTROMETER_API	bool	spec_get_curr_wave(int id, float* wave);

	SPECTROMETER_API	bool	spec_set_move_speed(int id, int grating, int speed);
	SPECTROMETER_API	bool	spec_get_move_speed(int id, int grating, int* speed);

	SPECTROMETER_API	bool	spec_set_filter_status(int id, int which, bool automatic);
	SPECTROMETER_API	bool	spec_get_filter_status(int id, int which, bool* automatic);

	SPECTROMETER_API	bool	spec_set_filter(int id, int which, int index);
	SPECTROMETER_API	bool	spec_get_filter(int id, int which, int* index);

	SPECTROMETER_API	bool	spec_set_filter_home(int id, int which);

	SPECTROMETER_API	bool	spec_set_filter_model(int id, const char* model);
	SPECTROMETER_API	bool	spec_get_filter_model(int id, char* model);

	SPECTROMETER_API	bool	spec_set_filter_limit(int id, int grating, short index, double val);
	SPECTROMETER_API	bool	spec_get_filter_limit(int id, int grating, short index, double* val);

	SPECTROMETER_API	bool	spec_set_exit_port(int id, bool front);
	SPECTROMETER_API	bool	spec_get_exit_port(int id, bool* front);

	SPECTROMETER_API	bool	spec_set_side_exit_pos(int id, int step);
	SPECTROMETER_API	bool	spec_get_side_exit_pos(int id, int* step);

	SPECTROMETER_API	bool	spec_set_entrance_port(int id, bool front);
	SPECTROMETER_API	bool	spec_get_entrance_port(int id, bool* front);

	SPECTROMETER_API	bool	spec_set_side_entrance_pos(int id, int step);
	SPECTROMETER_API	bool	spec_get_side_entrance_pos(int id, int* step);

	SPECTROMETER_API	bool	spec_get_mirror_model(int id, char* model);
	SPECTROMETER_API	bool	spec_set_mirror_model(int id, const char* model);

	SPECTROMETER_API	bool	spec_set_slit_width(int id, int index, int um);
	SPECTROMETER_API	bool	spec_get_slit_width(int id, int index, int* um);

	SPECTROMETER_API	bool	spec_set_slit_bandpass(int id, int index, float nm);
	SPECTROMETER_API	bool	spec_get_slit_bandpass(int id, int index, float* nm);

	SPECTROMETER_API	bool	spec_set_slit_zero_pos(int id, int index, int um);
	SPECTROMETER_API	bool	spec_get_slit_zero_pos(int id, int index, int* um);

	SPECTROMETER_API	bool	spec_set_slit_home(int id, int index);

	SPECTROMETER_API	bool	spec_set_slit_model(int id, char idx, const char* model);
	SPECTROMETER_API	bool	spec_get_slit_model(int id, char idx, char* model);

	SPECTROMETER_API	bool	spec_set_motor_steps(int id, int index, long steps);
	SPECTROMETER_API	bool	spec_get_motor_steps(int id, int index, long* steps);

	SPECTROMETER_API	bool	spec_set_motor_home(int id, int index);

	SPECTROMETER_API	bool	spec_set_motor_speed(int id, int index, int speed);
	SPECTROMETER_API	bool	spec_get_motor_speed(int id, int index, int* speed);

	SPECTROMETER_API	bool	spec_set_motor_home_dir(int id, int index, int dir);
	SPECTROMETER_API	bool	spec_get_motor_home_dir(int id, int index, int* dir);

	SPECTROMETER_API	bool	spec_set_motor_total_steps(int id, int index, long total);
	SPECTROMETER_API	bool	spec_get_motor_total_steps(int id, int index, long* total);

	SPECTROMETER_API	bool	spec_set_shutter_status(int id, int port, bool status);
	SPECTROMETER_API	bool	spec_get_shutter_status(int id, int port, bool* status);

	SPECTROMETER_API	bool	spec_is_setup_filter(int id, int index, bool* setup);
	SPECTROMETER_API	bool	spec_setup_filter(int id, int index, bool setup);

	SPECTROMETER_API	bool	spec_is_setup_mirror(int id, int index, bool* setup);
	SPECTROMETER_API	bool	spec_setup_mirror(int id, int index, bool setup);

	SPECTROMETER_API	bool	spec_is_setup_slit(int id, int index, bool* setup);
	SPECTROMETER_API	bool	spec_setup_slit(int id, int index, bool setup);

	SPECTROMETER_API	bool	spec_is_setup_shutter(int id, int index, bool* setup);
	SPECTROMETER_API	bool	spec_setup_shutter(int id, int index, bool setup);

	SPECTROMETER_API	bool	spec_set_correct_params(int id, int turret, int grating, int code, void* param);
	SPECTROMETER_API	bool	spec_get_correct_params(int id, int turret, int grating, int code, void* param);

	SPECTROMETER_API	float	spec_wave_to_step(int id, float wave);

	SPECTROMETER_API	bool	spec_pixels_to_waves(int id, int turret, int grating, float center_wave, int width, int count, int bin, float* result);

	SPECTROMETER_API	bool	spec_set_init_peripherals(int id, unsigned short peripherals);
	SPECTROMETER_API	bool	spec_get_init_peripherals(int id, unsigned short * peripherals);

	SPECTROMETER_API	bool	spec_set_peripherals_init_pos(int id, unsigned short peripheral, unsigned char pos);
	SPECTROMETER_API	bool	spec_get_peripherals_init_pos(int id, unsigned short peripheral, unsigned char * pos);

	SPECTROMETER_API	bool	spec_set_trig_out_interval(int id, unsigned short steps);
	SPECTROMETER_API	bool	spec_get_trig_out_interval(int id, unsigned short * steps);

	SPECTROMETER_API	bool	spec_set_trig_mode(int id, bool start);

	SPECTROMETER_API	bool	spec_set_trig_in_interval(int id, float nm);
	SPECTROMETER_API	bool	spec_get_trig_in_interval(int id, float * nm);

	SPECTROMETER_API	bool	spec_range_move(int id, float from_nm, float to_nm, float step_nm, int nm_s);
	SPECTROMETER_API	bool	spec_range_move2(int id, float from_nm, float to_nm, float step_nm, int delay_ms);

	SPECTROMETER_API	bool	spec_set_turret_enbale(int id, short number);
	SPECTROMETER_API	bool	spec_get_enbaled_turret(int id, short* number);

	SPECTROMETER_API	bool	spec_set_ccd_mode(int id, bool ccd_mode);
	SPECTROMETER_API	bool	spec_get_ccd_mode(int id);

	SPECTROMETER_API	bool	spec_init_spectral_splice(int id, float pixel_width, int pixel_count, int bin_x, float from, float to, float ref, int edge, float overlap, float* center_waves, int* waves_count);
	SPECTROMETER_API	bool	spec_spectral_splice(int id, float* x1, float* y1, int size1, float* x2, float* y2, int size2, float* x3, float* y3, int* size3);

	SPECTROMETER_API	bool	spec_set_user_data(int id, short offset, const unsigned char * data, short len);
	SPECTROMETER_API	bool	spec_get_user_data(int id, short offset, unsigned char * data, short len);

	SPECTROMETER_API	bool	spec_set_diaphragm(int id, int which, int where);
	SPECTROMETER_API	bool	spec_get_diaphragm(int id, int which, int* where);
	SPECTROMETER_API	bool	spec_set_diaphragm_steps(int id, int which, int where, long steps);
	SPECTROMETER_API	bool	spec_get_diaphragm_steps(int id, int which, int where, long* steps);

	SPECTROMETER_API	bool	spec_set_focus_mirror(int id, int where);
	SPECTROMETER_API	bool	spec_get_focus_mirror(int id, int* where);
	SPECTROMETER_API	bool	spec_set_focus_mirror_steps(int id, int where, long steps);
	SPECTROMETER_API	bool	spec_get_focus_mirror_steps(int id, int where, long* steps);
#ifdef __cplusplus
}
#endif
#endif // !_SPECTROMETER_H_

