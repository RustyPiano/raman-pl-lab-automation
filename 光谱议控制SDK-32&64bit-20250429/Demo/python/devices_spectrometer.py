# 光谱仪类-python封装，方便主程序调用，增加，修改功能
# 完善中，未封装全部的功能，可以按照动态库函数自行添加
# 2023-12-01
# Author: Mason Lei
import ctypes
from typing import Tuple


class DEV_info(ctypes.Structure):
    _fields_ = [
        ("manufacturer", ctypes.c_char*9),  # Manufacturer *最多 8 个字符*
        ("model", ctypes.c_char*24),        # Instrument model
        ("sn", ctypes.c_char*24),           # Serial number
        # Date of manufacture *年 4 个字符、月 2 个字符、日 2 个字符*
        ("date", ctypes.c_char*9),
        ("ver", ctypes.c_char*9)            # firmware version *固件版本,
    ]


class Spectrometer:
    def __init__(self):
        # python版本要和动态库版本一致，python为64位，则加载64位动态库
        self.spectrometer1 = ctypes.cdll.LoadLibrary(
            r'C:\Users\Administrator\Desktop\光谱仪sdk_新\x64\spectrometer_x64.dll')
        self.serial_no = None

    def __str__(self):
        return 'python api for zolix spectrometer.'

# ------设备连接基础-----------------------------------------------------
    def get_dll_ver(self, len1):
        """获取动态库的版本号
        输出，版本号"""
        self.spectrometer1.spec_get_dll_ver.argtypes = [
            ctypes.c_char_p, ctypes.c_int]
        self.spectrometer1.spec_get_dll_ver.restype = ctypes.c_void_p

        str_info = (ctypes.c_char*len1)()
        len1 = ctypes.c_int(len1)

        self.spectrometer1.spec_get_dll_ver(str_info, len1)
        # dll_ver_b = str_info.value
        # dll_ver = dll_ver_b.decode('utf-8')
        # dll_ver = dll_ver.replace('k', '')
        return str_info.value

    def enum_dev_count(self):
        """获取设备数量"""
        enum_dev = self.spectrometer1.spec_enum_dev_count()
        # print('设备数量：',enum_dev)
        return enum_dev

    def enum_dev_sn(self, index, len1):
        """获取设备型号
        输出，tt是否成功，dev_sn设备型号, len1为数据长度"""
        self.spectrometer1.spec_enum_dev_sn.argtypes = [
            ctypes.c_int, ctypes.c_char_p, ctypes.c_int]
        self.spectrometer1.spec_enum_dev_sn.restype = ctypes.c_bool

        a = ctypes.c_int(index)
        str_info = (ctypes.c_char*len1)()
        len1_1 = ctypes.c_int(len1)

        tt = self.spectrometer1.spec_enum_dev_sn(a, str_info, len1_1)
        # dev_sn_b = str_info.value
        # dev_sn = dev_sn_b.decode('utf-8')
        # dev_sn = dev_sn.replace('k', '')
        # print('设备型号：',dev_sn)
        return tt, str_info.value

    def open(self, dev_sn):
        """打开谱仪,返回序列号"""
        self.spectrometer1.spec_open.argtypes = [ctypes.c_char_p]
        self.spectrometer1.spec_open.restype = ctypes.c_int

        dev_sn_1 = ctypes.c_char_p(dev_sn)
        serial_no = self.spectrometer1.spec_open(dev_sn_1)
        # print('设备序列号',serial_no)
        self.serial_no = serial_no
        return serial_no

    def close(self, id1: int) -> bool:
        """关闭谱仪"""
        self.spectrometer1.spec_close.argtypes = [ctypes.c_int]
        self.spectrometer1.spec_close.restype = ctypes.c_bool

        serial_no_2 = ctypes.c_int(id1)
        is_close = self.spectrometer1.spec_close(serial_no_2)
        # print('是否正确关闭:',is_close)
        return is_close

    def get_is_open(self, id1: int) -> bool:
        """检测谱仪是否正常打开,id1为谱仪序列号，小于0代表无效"""
        self.spectrometer1.spec_get_is_open.argtypes = [ctypes.c_int]
        self.spectrometer1.spec_get_is_open.restype = ctypes.c_bool

        serial_no_1 = ctypes.c_int(id1)
        is_open = self.spectrometer1.spec_get_is_open(serial_no_1)
        # print('是否正常连接',is_open)
        return is_open

    def get_error(self, id1: int):
        """检测谱仪是否正常打开,id1为谱仪序列号，小于0代表无效"""
        self.spectrometer1.spec_get_error.argtypes = [
            ctypes.c_int, ctypes.c_char_p]
        self.spectrometer1.spec_get_error.restype = ctypes.c_bool

        serial_no_1 = ctypes.c_int(id1)
        str_info = ctypes.create_string_buffer(b'kkkkkkkkkkk')

        tt = self.spectrometer1.spec_get_error(serial_no_1, str_info)
        error_code_b = str_info.value
        error_code = error_code_b.decode('utf-8')
        error_code = error_code.replace('k', '')
        # print('设备型号：',dev_sn)
        return tt, error_code

# -------基本设置--------------------------------------------
    def set_timeout(self, id1: int, ms_read, ms_write) -> bool:
        """设备读写超时设置。默认20 s上限
        通常不需要设置
        参数：
        id1 : 设备的ID。
        ms_read: 读设备的时间上限。
        ms_write：写设备的时间上限。
        返回值：
        true: 完成设备读写超时设置。
        false: 设备ID有误，读写超时设置失败。"""
        self.spectrometer1.spec_set_timeout.argtypes = [
            ctypes.c_int, ctypes.c_int, ctypes.c_int]
        self.spectrometer1.spec_set_timeout.restype = ctypes.c_bool

        serial_no_1 = ctypes.c_int(id1)
        ms_read_1 = ctypes.c_int(ms_read)
        ms_write_1 = ctypes.c_int(ms_write)
        is_set_ok = self.spectrometer1.spec_set_timeout(
            serial_no_1, ms_read_1, ms_write_1)
        return is_set_ok

    def set_dev_info(self, id1: int, info: DEV_info):
        """设置设备信息，设备信息类型请参阅DEV_info类"""
        self.spectrometer1.spec_set_dev_info.argtypes = [
            ctypes.c_int, DEV_info]
        self.spectrometer1.spec_set_dev_info.restype = ctypes.c_bool

        serial_no_1 = ctypes.c_int(id1)
        issuccess = self.spectrometer1.spec_set_dev_info(serial_no_1, info)
        # if issuccess:
        #     print('设置设备信息成功！')
        return issuccess

    def get_dev_info(self, id1: int):
        """获取设备信息，设备信息请参阅DEV_info类"""
        self.spectrometer1.spec_get_dev_info.argtypes = [
            ctypes.c_int, ctypes.POINTER(DEV_info)]
        self.spectrometer1.spec_get_dev_info.restype = ctypes.c_bool

        info = DEV_info(b'Zolix', b'AAAAA', b'22222', b'2022222', b'0.0')

        serial_no_1 = ctypes.c_int(id1)
        issuccess = self.spectrometer1.spec_get_dev_info(
            serial_no_1, ctypes.byref(info))
        # if issuccess:
        #     print(info)
        return issuccess, info.value

    def backup(self, id1: int) -> bool:
        """备份单色仪所有光栅的参数。参数包括光栅台号、光栅号、零级位置、校正系数 光栅刻线数、闪耀波长、定位位置等
        参数：
        id1 : 单色仪的ID。
        返回值：
        true: 成功备份单色仪所有光栅的参数。
        false: 设备ID有误，备份失败。"""
        self.spectrometer1.spec_backup.argtypes = [
            ctypes.c_int]
        self.spectrometer1.spec_backup.restype = ctypes.c_bool

        serial_no_1 = ctypes.c_int(id1)
        is_set_ok = self.spectrometer1.spec_backup(serial_no_1)
        return is_set_ok

    def restore(self, id1: int) -> bool:
        """恢复出厂设置。重新设置单色仪参数为出厂设置值
        参数：
        id1 : 单色仪的ID。
        返回值：
        true: 成功设置单色仪参数为出厂设置值。
        false: 设备ID有误，恢复出厂设置失败。"""
        self.spectrometer1.spec_restore.argtypes = [
            ctypes.c_int]
        self.spectrometer1.spec_restore.restype = ctypes.c_bool

        serial_no_1 = ctypes.c_int(id1)
        is_set_ok = self.spectrometer1.spec_restore(serial_no_1)

        return is_set_ok

# -------总电机步数-------------------------------------------------
    def set_totalsteps(self, id1: int, steps) -> bool:
        """设置光栅台转一圈的总步数
        id1 : 单色仪的ID。
        step : 光栅台转一圈的总步数。
        返回值：
        true: 成功设置光栅台转一圈的总步数。
        false: 设备ID有误，设置失败。"""
        self.spectrometer1.spec_set_total_steps.argtypes = [
            ctypes.c_int, ctypes.c_long]
        self.spectrometer1.spec_set_total_steps.restype = ctypes.c_bool

        serial_no_1 = ctypes.c_int(id1)
        steps_1 = ctypes.c_long(steps)
        is_set_ok = self.spectrometer1.spec_set_total_steps(
            serial_no_1, steps_1)

        return is_set_ok

    def get_totalsteps(self, id1: int):
        """获取谱仪总电机步数
        参数：
        id1 : 单色仪的ID。
        steps : 光栅台转一圈的总步数。
        返回值：
        true: 成功获取光栅台转一圈的总步数。
        false: 设备ID有误，设置失败。"""
        self.spectrometer1.spec_get_total_steps.argtypes = [
            ctypes.c_int, ctypes.POINTER(ctypes.c_long)]
        self.spectrometer1.spec_get_total_steps.restype = ctypes.c_bool

        serial_no_3 = ctypes.c_int(id1)
        steps_1 = ctypes.c_long(888)
        is_true = self.spectrometer1.spec_get_total_steps(
            serial_no_3, ctypes.byref(steps_1))

        return is_true, steps_1.value

# -------IO输出-------------------------------------------------
    def set_io_output(self, id1: int, grating_no):
        # 缺省
        pass

    def get_io_output(self, id1: int):
        # 缺省
        pass

# -------塔台设置-------------------------------------------------
    def set_turret(self, id1: int, turret_num) -> bool:
        """设置目前安装的塔台号
        参数：
        id1 : 单色仪的ID。
        num : 塔台号, 范围为1~3。
        返回值：
        true: 成功设置目前安装的光栅台号。
        false: 设备ID有误或光栅台号超出范围，设置失败。"""
        self.spectrometer1.spec_set_turret.argtypes = [
            ctypes.c_int, ctypes.c_int]
        self.spectrometer1.spec_set_turret.restype = ctypes.c_bool

        serial_no_3 = ctypes.c_int(id1)
        turret_num_1 = ctypes.c_int(turret_num)
        is_true = self.spectrometer1.spec_set_turret(
            serial_no_3, turret_num_1)
        return is_true

    def get_turret(self, id1: int):
        """读取目前安装的塔台号
        参数：
        id1 : 单色仪的ID。
        num : 塔台号, 范围为1~3。
        返回值：
        true: 成功设置目前安装的光栅台号。
        false: 设备ID有误或光栅台号超出范围，设置失败。"""
        self.spectrometer1.spec_get_turret.argtypes = [
            ctypes.c_int, ctypes.POINTER(ctypes.c_int)]
        self.spectrometer1.spec_get_turret.restype = ctypes.c_bool

        serial_no_3 = ctypes.c_int(id1)
        turret_num_1 = ctypes.c_int(888)

        is_true = self.spectrometer1.spec_get_turret(
            serial_no_3, ctypes.byref(turret_num_1))
        return is_true, turret_num_1.value

# -------零级位置-------------------------------------------------
    def set_zero_pos(self, id1: int, grating_no, step) -> bool:
        """设置光栅零级位置参数-单色仪使用
        参数：
        id1 : 单色仪的ID。
        grating : 设置的光栅号，范围为1~仪器光栅数。
        step : 目标光栅的零级位置，范围为 0~光栅总步数。
        返回值：
        true: 成功设置光栅零级位置参数。
        false: 设置失败。"""
        self.spectrometer1.spec_set_zero_pos.argtypes = [
            ctypes.c_int, ctypes.c_int, ctypes.c_long]
        self.spectrometer1.spec_set_zero_pos.restype = ctypes.c_bool

        serial_no_3 = ctypes.c_int(id1)
        grating_no = ctypes.c_int(grating_no)
        step_1 = ctypes.c_long(step)

        is_true = self.spectrometer1.spec_set_zero_pos(
            serial_no_3, grating_no, step_1)
        return is_true

    def get_zero_pos(self, id1: int, grating_no):
        """读取光栅零级位置参数-单色仪使用
        参数：
        id1 : 单色仪的ID。
        grating : 设置的光栅号，范围为1~仪器光栅数。
        step : 目标光栅的零级位置，范围为 0~光栅总步数。
        返回值：
        true: 成功设置光栅零级位置参数。
        false: 设置失败。"""
        self.spectrometer1.spec_get_zero_pos.argtypes = [
            ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_long)]
        self.spectrometer1.spec_get_zero_pos.restype = ctypes.c_bool

        serial_no_3 = ctypes.c_int(id1)
        grating_no_1 = ctypes.c_int(grating_no)
        step_1 = ctypes.c_long(888)
        is_true = self.spectrometer1.spec_get_zero_pos(
            serial_no_3, grating_no_1, ctypes.byref(step_1))
        return is_true, step_1.value

    def set_zero_offset(self, id1: int, grating_no, step) -> bool:
        """设置光栅零级位置偏置, 用于校正波长偏差，偏差值适用于当前出口，切换出口后，
        如果仍有偏差需重新设置，仅适用于HiperS-320i。_单色仪形式用
        参数：
        id1 : 单色仪的ID。
        grating : 设置的光栅号，范围为1~仪器光栅数。
        step : 目标光栅的零级偏置，范围为 0~光栅总步数。
        返回值：
        true: 成功设置光栅零级偏置。
        false: 设置失败。"""
        self.spectrometer1.spec_set_zero_offset.argtypes = [
            ctypes.c_int, ctypes.c_int, ctypes.c_long]
        self.spectrometer1.spec_set_zero_offset.restype = ctypes.c_bool

        serial_no_3 = ctypes.c_int(id1)
        grating_no = ctypes.c_int(grating_no)
        step_1 = ctypes.c_long(step)
        is_true = self.spectrometer1.spec_set_zero_offset(
            serial_no_3, grating_no, step_1)
        return is_true

    def get_zero_offset(self, id1: int, grating_no):
        """读取光栅零级位置偏置, 用于校正波长偏差，偏差值适用于当前出口，切换出口后，
        如果仍有偏差需重新设置，仅适用于HiperS-320i。_单色仪形式用
        参数：
        id1 : 单色仪的ID。
        grating : 设置的光栅号，范围为1~仪器光栅数。
        step : 目标光栅的零级偏置，范围为 0~光栅总步数。
        返回值：
        true: 成功设置光栅零级偏置。
        false: 设置失败。"""
        self.spectrometer1.spec_get_zero_offset.argtypes = [
            ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_long)]
        self.spectrometer1.spec_get_zero_offset.restype = ctypes.c_bool

        serial_no_3 = ctypes.c_int(id1)
        grating_no_1 = ctypes.c_int(grating_no)
        step_1 = ctypes.c_long(888)
        is_true = self.spectrometer1.spec_get_zero_offset(
            serial_no_3, grating_no_1, ctypes.byref(step_1))
        return is_true, step_1.value

    def set_adjustment(self, id1: int, grating_no, val) -> bool:
        """设置光栅的校正系数参数
        参数：
        id1 : 单色仪的ID。
        grating : 设置的光栅号，范围为1~仪器光栅数。
        val : 设置的光栅校正系数参数。
        返回值：
        true: 成功设置光栅校正系数参数。
        false: 设置失败。"""
        self.spectrometer1.spec_set_adjustment.argtypes = [
            ctypes.c_int, ctypes.c_int, ctypes.c_float]
        self.spectrometer1.spec_set_adjustment.restype = ctypes.c_bool

        serial_no_3 = ctypes.c_int(id1)
        grating_no = ctypes.c_int(grating_no)
        val_1 = ctypes.c_float(val)
        is_true = self.spectrometer1.spec_set_adjustment(
            serial_no_3, grating_no, val_1)
        return is_true

    def get_adjustment(self, id1: int, grating_no):
        """读取光栅的校正系数参数
        参数：
        id1 : 单色仪的ID。
        grating : 设置的光栅号，范围为1~仪器光栅数。
        val : 设置的光栅校正系数参数。
        返回值：
        true: 成功设置光栅校正系数参数。
        false: 设置失败。"""
        self.spectrometer1.spec_get_adjustment.argtypes = [
            ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_float)]
        self.spectrometer1.spec_get_adjustment.restype = ctypes.c_bool

        serial_no_3 = ctypes.c_int(id1)
        grating_no_1 = ctypes.c_int(grating_no)
        val_1 = ctypes.c_float(444.44)

        is_true = self.spectrometer1.spec_get_adjustment(
            serial_no_3, grating_no_1, ctypes.byref(val_1))
        return is_true, val_1.value

    def get_max_wavelength(self, id1: int, grating):
        """获取谱仪当前光栅可达到的最大波长值"""
        self.spectrometer1.spec_get_max_wavelength.argtypes = [
            ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_float)]
        self.spectrometer1.spec_get_max_wavelength.restype = ctypes.c_bool

        serial_no_3 = ctypes.c_int(id1)
        grating_no = ctypes.c_int(grating)
        max_wavelength = ctypes.c_float(888.88)

        is_true = self.spectrometer1.spec_get_max_wavelength(
            serial_no_3, grating_no, ctypes.byref(max_wavelength))
        return is_true, max_wavelength.value

    def spec_adjusting(self, id1: int, grating_no, wave_set, wave_real):
        """计算光栅校正系数
        参数：
        id1 : 单色仪的ID。
        grating : 读取的光栅号，范围为1~仪器光栅数。
        wave_set : 特征峰的理论波长值。
        wave_real : 特征峰的实测波长值。
        result : 光栅校正系数。
        返回值：
        true: 成功计算光栅的校正系数。
        false: 计算失败。"""
        self.spectrometer1.spec_adjusting.argtypes = [
            ctypes.c_int, ctypes.c_int, ctypes.c_float, ctypes.c_float, ctypes.POINTER(ctypes.c_float)]
        self.spectrometer1.spec_adjusting.restype = ctypes.c_bool

        serial_no_3 = ctypes.c_int(id1)
        grating_no = ctypes.c_int(grating_no)
        wave_set_1 = ctypes.c_float(wave_set)
        wave_real_1 = ctypes.c_float(wave_real)
        result_1 = ctypes.c_float(8888.88)

        is_true = self.spectrometer1.spec_adjusting(
            serial_no_3, grating_no, wave_set_1, wave_real_1, ctypes.byref(result_1))
        return is_true, result_1.value

# -------光栅信息设置------------------------------------------------
    def set_grating_info(self, id1: int, grating_no, groove, blaze) -> bool:
        """设置光栅刻线数及闪耀波长
        参数：
        id1 : 单色仪的ID。
        grating :光栅号，范围为1~仪器光栅数。
        groove : 设置的刻线数。
        blaze : 设置的闪耀波长。
        返回值：
        true: 成功设置光栅刻线数及闪耀波长。
        false: 设置失败。"""
        self.spectrometer1.spec_set_grating_info.argtypes = [
            ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_long]
        self.spectrometer1.spec_set_grating_info.restype = ctypes.c_bool

        serial_no_3 = ctypes.c_int(id1)
        grating_no_1 = ctypes.c_int(grating_no)
        groove_1 = ctypes.c_int(groove)
        blaze_1 = ctypes.c_long(blaze)
        is_true = self.spectrometer1.spec_set_grating_info(
            serial_no_3, grating_no_1, groove_1, blaze_1)
        return is_true

    def get_grating_info(self, id1: int, grating_no):
        """读取光栅刻线数及闪耀波长
        参数：
        id1 : 单色仪的ID。
        grating :光栅号，范围为1~仪器光栅数。
        groove : 设置的刻线数。
        blaze : 设置的闪耀波长。
        返回值：
        true: 成功设置光栅刻线数及闪耀波长。
        false: 设置失败。"""
        self.spectrometer1.spec_get_grating_info.argtypes = [
            ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_long)]
        self.spectrometer1.spec_get_grating_info.restype = ctypes.c_bool

        serial_no_3 = ctypes.c_int(id1)
        grating_no_1 = ctypes.c_int(grating_no)
        groove_1 = ctypes.c_int(100)
        blaze_1 = ctypes.c_long(350)
        is_true = self.spectrometer1.spec_get_grating_info(
            serial_no_3, grating_no_1, ctypes.byref(groove_1), ctypes.byref(blaze_1))
        return is_true, groove_1.value, blaze_1.value

    def set_init_grating(self, id1: int, grating_no) -> bool:
        """设置开机初始化时光栅位置
        参数：
        id1 : 单色仪的ID。
        grating : 光栅号，范围为1~仪器光栅数。
        返回值：
        true: 成功设置开机初始化时光栅位置。
        false: 设置失败。"""
        self.spectrometer1.spec_set_init_grating.argtypes = [
            ctypes.c_int, ctypes.c_int]
        self.spectrometer1.spec_set_init_grating.restype = ctypes.c_bool

        serial_no_3 = ctypes.c_int(id1)
        grating_no = ctypes.c_int(grating_no)
        is_true = self.spectrometer1.spec_set_init_grating(
            serial_no_3, grating_no)
        return is_true

    def get_init_grating(self, id1: int):
        """设置开机初始化时光栅位置
        参数：
        id1 : 单色仪的ID。
        grating : 光栅号，范围为1~仪器光栅数。
        返回值：
        true: 成功设置开机初始化时光栅位置。
        false: 设置失败。"""
        self.spectrometer1.spec_get_init_grating.argtypes = [
            ctypes.c_int, ctypes.POINTER(ctypes.c_int)]
        self.spectrometer1.spec_get_init_grating.restype = ctypes.c_bool

        serial_no_3 = ctypes.c_int(id1)
        grating_no_1 = ctypes.c_int(99)

        is_true = self.spectrometer1.spec_get_init_grating(
            serial_no_3, ctypes.byref(grating_no_1))
        return is_true, grating_no_1.value

    def set_init_wave(self, id1: int, grating_no, wave) -> bool:
        """设置切换光栅时，光栅的定位位置
        参数：
        id1 : 单色仪的ID。
        grating : 光栅号，范围为1~仪器光栅数。
        wave : 光栅的位置。单位为nm。
        返回值：
        true: 成功设置切换光栅时光栅的定位位置。
        false: 设置失败。"""
        self.spectrometer1.spec_set_init_wave.argtypes = [
            ctypes.c_int, ctypes.c_int, ctypes.c_float]
        self.spectrometer1.spec_set_init_wave.restype = ctypes.c_bool

        serial_no_3 = ctypes.c_int(id1)
        grating_no_1 = ctypes.c_int(grating_no)
        wave_1 = ctypes.c_float(wave)

        is_true = self.spectrometer1.spec_set_init_wave(
            serial_no_3, grating_no_1, wave_1)
        return is_true

    def get_init_wave(self, id1: int, grating_no):
        """读取切换光栅时，光栅的定位位置
        参数：
        id1 : 单色仪的ID。
        grating : 光栅号，范围为1~仪器光栅数。
        wave : 光栅的位置。单位为nm。
        返回值：
        true: 成功设置切换光栅时光栅的定位位置。
        false: 设置失败。"""
        self.spectrometer1.spec_get_init_wave.argtypes = [
            ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_float)]
        self.spectrometer1.spec_get_init_wave.restype = ctypes.c_bool

        serial_no_3 = ctypes.c_int(id1)
        grating_no_1 = ctypes.c_int(grating_no)
        wave_1 = ctypes.c_float(88.88)

        is_true = self.spectrometer1.spec_get_init_wave(
            serial_no_3, grating_no_1, ctypes.byref(wave_1))
        return is_true, wave_1.value

    def set_dispersion(self, id1: int, val) -> bool:
        """设置单色仪倒线色散参数
        参数：
        id1 : 单色仪的ID。
        val : 单色仪倒线色散参数，单位为nm/mm。
        返回值：
        true: 成功设置单色仪倒线色散参数。
        false: 设置失败。"""
        self.spectrometer1.spec_set_dispersion.argtypes = [
            ctypes.c_int, ctypes.c_float]
        self.spectrometer1.spec_set_dispersion.restype = ctypes.c_bool

        serial_no_3 = ctypes.c_int(id1)
        val_1 = ctypes.c_float(val)
        is_true = self.spectrometer1.spec_set_dispersion(
            serial_no_3, val_1)
        return is_true

    def get_dispersion(self, id1: int):
        """读取单色仪倒线色散参数
        参数：
        id1 : 单色仪的ID。
        val : 单色仪倒线色散参数，单位为nm/mm。
        返回值：
        true: 成功设置单色仪倒线色散参数。
        false: 设置失败。"""
        self.spectrometer1.spec_get_dispersion.argtypes = [
            ctypes.c_int, ctypes.POINTER(ctypes.c_float)]
        self.spectrometer1.spec_get_dispersion.restype = ctypes.c_bool

        serial_no_3 = ctypes.c_int(id1)
        val_1 = ctypes.c_float(888.88)
        is_true = self.spectrometer1.spec_get_dispersion(
            serial_no_3, ctypes.byref(val_1))
        return is_true, val_1.value

    def set_grating_home(self, id1: int) -> bool:
        """设置当前光栅归零"""
        self.spectrometer1.spec_set_grating_home.argtypes = [
            ctypes.c_int]
        self.spectrometer1.spec_set_grating_home.restype = ctypes.c_bool

        serial_no_1 = ctypes.c_int(id1)
        is_set_ok = self.spectrometer1.spec_move_steps(serial_no_1)

        return is_set_ok

    def get_grating_count(self, id1: int):
        """获取谱仪的光栅数量"""
        self.spectrometer1.spec_get_grating_count.argtypes = [
            ctypes.c_int, ctypes.POINTER(ctypes.c_short)]
        self.spectrometer1.spec_get_grating_count.restype = ctypes.c_bool

        serial_no_3 = ctypes.c_int(id1)
        grating_count = ctypes.c_short(8)
        is_true = self.spectrometer1.spec_get_grating_count(
            serial_no_3, ctypes.byref(grating_count))
        return is_true, grating_count.value

    def set_grating(self,  grating_no) -> bool:
        """设置或旋转到几号光栅"""
        self.spectrometer1.spec_set_grating.argtypes = [
            ctypes.c_int, (ctypes.c_int)]
        self.spectrometer1.spec_set_grating.restype = ctypes.c_bool

        # serial_no_3 = ctypes.c_int(id1)
        grating_no = ctypes.c_int(grating_no)

        if self.serial_no is not None:
            is_true = self.spectrometer1.spec_set_grating(
                self.serial_no, (grating_no))
            # print('设置光栅序号为：{0}, 是否成功:{1}'.format( grating_no.value, is_true))
            return is_true
        else:
            return 'can not find device id'

    def get_grating(self, id1: int):
        """获取当前光栅号"""
        self.spectrometer1.spec_get_grating.argtypes = [
            ctypes.c_int, ctypes.POINTER(ctypes.c_int)]
        self.spectrometer1.spec_get_grating.restype = ctypes.c_bool

        serial_no_3 = ctypes.c_int(id1)
        grating_no_1 = ctypes.c_int(888)
        # grating_no =  ctypes.POINTER(tt3)
        is_true = self.spectrometer1.spec_get_grating(
            serial_no_3, ctypes.byref(grating_no_1))

        return is_true, grating_no_1.value


# -------谱仪移动，转动方式--------------------------------------------------------


    def move_wave(self, id1: int, wave) -> bool:
        """谱仪移动相对波长"""
        self.spectrometer1.spec_move_wave.argtypes = [
            ctypes.c_int, ctypes.c_float]
        self.spectrometer1.spec_move_wave.restype = ctypes.c_bool

        serial_no_3 = ctypes.c_int(id1)
        wave1 = ctypes.c_float(wave)
        ismovesuccess = self.spectrometer1.spec_move_wave(
            serial_no_3, wave1)
        return ismovesuccess

    def move_to_wave(self,  wave) -> bool:
        """谱仪移动到指定波长位置"""
        self.spectrometer1.spec_move_to_wave.argtypes = [
            ctypes.c_int, ctypes.c_float]
        self.spectrometer1.spec_move_to_wave.restype = ctypes.c_bool

        # serial_no_3 = ctypes.c_int(id1)
        if self.serial_no is not None:
            wave1 = ctypes.c_float(wave)
            ismovesuccess = self.spectrometer1.spec_move_to_wave(
                self.serial_no, wave1)
            return ismovesuccess
        else:
            return 'can not find device id'

    def get_cur_steps(self, id1: int):
        """获取当前电机步数"""
        self.spectrometer1.spec_get_cur_steps.argtypes = [
            ctypes.c_int, ctypes.POINTER(ctypes.c_float)]
        self.spectrometer1.spec_get_cur_steps.restype = ctypes.c_bool

        serial_no_3 = ctypes.c_int(id1)
        cur_step = ctypes.c_float(0.0)
        # grating_no =  ctypes.POINTER(tt3)
        is_true = self.spectrometer1.spec_get_cur_steps(
            serial_no_3, ctypes.byref(cur_step))

        return is_true, cur_step.value

    def move_steps(self, id1: int, steps) -> bool:
        """移动电机步数，相对移动"""
        self.spectrometer1.spec_move_steps.argtypes = [
            ctypes.c_int, ctypes.c_float]
        self.spectrometer1.spec_move_steps.restype = ctypes.c_bool

        serial_no_2 = ctypes.c_int(id1)
        steps_to_go = ctypes.c_float(steps)

        is_move = self.spectrometer1.spec_move_steps(serial_no_2, steps_to_go)
        # print('直出口设置：', is_set)
        return is_move

    def move_to_steps(self, id1: int, steps) -> bool:
        """移动电机步数，绝对位置移动"""
        self.spectrometer1.spec_move_to_steps.argtypes = [
            ctypes.c_int, ctypes.c_float]
        self.spectrometer1.spec_move_to_steps.restype = ctypes.c_bool

        serial_no_2 = ctypes.c_int(id1)
        exit_port = ctypes.c_float(steps)

        is_move = self.spectrometer1.spec_move_to_steps(serial_no_2, exit_port)
        # print('直出口设置：', is_set)
        return is_move

    def get_curr_wave(self, id1: int):
        """获取当前光栅号"""
        self.spectrometer1.spec_get_curr_wave.argtypes = [
            ctypes.c_int, ctypes.POINTER(ctypes.c_int)]
        self.spectrometer1.spec_get_curr_wave.restype = ctypes.c_bool

        serial_no_3 = ctypes.c_int(id1)
        grating_no_1 = ctypes.c_int(888)
        # grating_no =  ctypes.POINTER(tt3)
        is_true = self.spectrometer1.spec_get_curr_wave(
            serial_no_3, ctypes.byref(grating_no_1))
        return grating_no_1.value

    def set_move_speed(self, id1: int, grating_no, speed) -> bool:
        """设置单色仪移动速度。 谨慎修改，运动速度过快会影响波长准确度
        id1 : 单色仪的ID。
        grating : 单色仪的光栅号，范围为1~仪器光栅数。
        speed : 移动速度，单位nm/s
        返回值：
        true: 成功设置单色仪移动速度。
        false: 设置失败。"""
        self.spectrometer1.spec_set_move_speed.argtypes = [
            ctypes.c_int, ctypes.c_int, ctypes.c_int]
        self.spectrometer1.spec_set_move_speed.restype = ctypes.c_bool

        serial_no_3 = ctypes.c_int(id1)
        grating_no = ctypes.c_int(grating_no)
        speed_1 = ctypes.c_int(speed)
        is_true = self.spectrometer1.spec_set_move_speed(
            serial_no_3, grating_no, speed_1)
        return is_true

    def get_move_speed(self, id1: int, grating_no):
        """读取单色仪的运动速度
        id1 : 单色仪的ID。
        grating : 单色仪的光栅号，范围为1~仪器光栅数。
        speed : 移动速度，单位nm/s
        返回值：
        true: 成功设置单色仪移动速度。
        false: 设置失败。"""
        self.spectrometer1.spec_get_move_speed.argtypes = [
            ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_int)]
        self.spectrometer1.spec_get_move_speed.restype = ctypes.c_bool

        serial_no_3 = ctypes.c_int(id1)
        grating_no_1 = ctypes.c_int(grating_no)
        speed_1 = ctypes.c_int(1.0)
        is_true = self.spectrometer1.spec_get_move_speed(
            serial_no_3, grating_no_1, ctypes.byref(speed_1))
        return is_true, speed_1.value

# ---滤光片轮相关------------------------------------------------
    def set_filter_status(self, id1: int, index, automatic) -> None:
        """设置滤光片轮状态，True自动模式，false手动模式
        参数：
        id1 : 单色仪的ID。
        index: 0-外置滤光片轮, 1-内置滤光片轮。
        automatic : 是否自动选择滤光片轮的标志位。可能值及其意义：
        true: 根据波长自动选择滤光片轮。
        false: 取消根据波长自动选择滤光片轮。
        返回值：
        无返回值。"""
        self.spectrometer1.spec_set_filter_status.argtypes = [
            ctypes.c_int, ctypes.c_int, ctypes.c_bool]
        self.spectrometer1.spec_set_filter_status.restype = ctypes.c_bool

        serial_no_2 = ctypes.c_int(id1)
        index_1 = ctypes.c_int(index)
        automatic_b = ctypes.c_bool(automatic)

        state = self.spectrometer1.spec_set_filter_status(
            serial_no_2, index_1, automatic_b)
        return state

    def get_filter_status(self, id1: int, index):
        """获取滤光片轮的切换方式
        参数：
        id1 : 单色仪的ID。
        index: 0-外置滤光片轮, 1-内置滤光片轮。
        automatic : 滤光片轮的选择方式。可能值及其意义：
        true: 根据波长自动选择滤光片轮。
        false: 手动选择滤光片轮。
        返回值：
        无返回值。"""
        self.spectrometer1.spec_get_filter_status.argtypes = [
            ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_bool)]
        self.spectrometer1.spec_get_filter_status.restype = ctypes.c_void_p

        serial_no_3 = ctypes.c_int(id1)
        index_1 = ctypes.c_int(index)
        automatic_b = ctypes.c_bool(True)

        self.spectrometer1.spec_get_filter_status(
            serial_no_3, index_1, ctypes.byref(automatic_b))
        return automatic_b.value

    def set_filter(self, id1: int, index, which) -> bool:
        """手动切换滤光片轮位置
        参数：
        id1 : 单色仪的ID。
        index: 0-外置滤光片轮, 1-内置滤光片轮。
        which: 滤光片轮的序号，范围为1~6。
        返回值：
        true: 成功手动选择滤光片轮。
        false: 或者滤光片轮序号超出范围。"""
        self.spectrometer1.spec_set_filter.argtypes = [
            ctypes.c_int, ctypes.c_int, ctypes.c_int]
        self.spectrometer1.spec_set_filter.restype = ctypes.c_bool

        serial_no_2 = ctypes.c_int(id1)
        index_1 = ctypes.c_int(index)
        which_1 = ctypes.c_int(which)

        is_set_ok = self.spectrometer1.spec_set_filter(
            serial_no_2, index_1, which_1)
        return is_set_ok

    def get_filter(self, id1: int, index):
        """读取当前滤光片轮的位置
        参数：
        id1 : 单色仪的ID。
        index: 0-外置滤光片轮, 1-内置滤光片轮。
        which: 滤光片轮的序号，范围为1~6。
        返回值：
        true: 成功读取选择的滤光片轮的序号。
        false: 读取失败。"""
        self.spectrometer1.spec_get_filter.argtypes = [
            ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_int)]
        self.spectrometer1.spec_get_filter.restype = ctypes.c_bool

        serial_no_3 = ctypes.c_int(id1)
        index_1 = ctypes.c_int(index)
        which_1 = ctypes.c_int(9)
        is_true = self.spectrometer1.spec_get_filter(
            serial_no_3, index_1, ctypes.byref(which_1))
        return is_true, which_1.value

    def set_filter_home(self, id1: int, index) -> bool:
        """滤光片轮位置归零
        参数：
        id1 : 单色仪的ID。
        index: 0-外置滤光片轮, 1-内置滤光片轮。
        返回值：
        true: 成功将单色仪的滤光片轮重新定位到机械零点。
        false: 设置失败。"""
        self.spectrometer1.spec_set_filter_home.argtypes = [
            ctypes.c_int, ctypes.c_int]
        self.spectrometer1.spec_set_filter_home.restype = ctypes.c_bool

        serial_no_2 = ctypes.c_int(id1)
        index_1 = ctypes.c_int(index)

        is_set_ok = self.spectrometer1.spec_set_filter_home(
            serial_no_2, index_1)
        return is_set_ok

    def set_filter_model(self, id1: int, model) -> bool:
        """设置滤光片轮型号
        参数：
        id1 : 单色仪的ID。
        model : 滤光片轮型号。可能值为SD和SR-SD。
        返回值：
        true: 成功设置滤光片轮型号。
        false: 设置失败。"""
        self.spectrometer1.spec_set_filter_model.argtypes = [
            ctypes.c_int, ctypes.c_char_p]
        self.spectrometer1.spec_set_filter_model.restype = ctypes.c_bool

        serial_no_3 = ctypes.c_int(id1)
        model_1 = model.encode()
        model_2 = ctypes.c_char_p(model_1)
        is_true = self.spectrometer1.spec_set_filter_model(
            serial_no_3, model_2)

        return is_true

    def get_filter_model(self, id1: int):
        """读取滤光片轮型号
        参数：
        id1 : 单色仪的ID。
        model : 滤光片轮型号。可能值为SD和SR-SD。
        返回值：
        true: 成功读取滤光片轮型号。
        false: 读取失败。"""
        self.spectrometer1.spec_get_filter_model.argtypes = [
            ctypes.c_int, ctypes.c_char_p]
        self.spectrometer1.spec_get_filter_model.restype = ctypes.c_bool

        serial_no_3 = ctypes.c_int(id1)
        model_1 = (ctypes.c_char*10)()

        is_true = self.spectrometer1.spec_get_filter_model(
            serial_no_3, model_1)
        return is_true, model_1.value

    def set_filter_limit(self, id1: int, grating_no, which, val) -> bool:
        """设置滤光片有效波长起始位置
        参数：
        id1 : 单色仪的ID。
        grating : 单色仪的光栅号，范围为1~仪器光栅数。
        which: 滤光片轮的序号，范围为1~6。
        val : 滤光片有效波长起始位置。
        返回值：
        true: 成功设置滤光片有效波长起始位置。
        false: 单色仪ID、光栅号和滤光片轮序号至少一个有误，设置失败。"""
        self.spectrometer1.spec_set_filter_limit.argtypes = [
            ctypes.c_int, ctypes.c_int, ctypes.c_short, ctypes.c_double]
        self.spectrometer1.spec_set_filter_limit.restype = ctypes.c_bool

        serial_no_3 = ctypes.c_int(id1)
        grating_no_1 = ctypes.c_int(grating_no)
        which_1 = ctypes.c_short(which)
        val_1 = ctypes.c_double(val)
        is_true = self.spectrometer1.spec_set_filter_limit(
            serial_no_3, grating_no_1, which_1, val_1)

        return is_true

    def get_filter_limit(self, id1: int, grating_no, which):
        """读取滤光片有效波长起始位置。
        参数：
        id1 : 单色仪的ID。
        grating : 单色仪的光栅号，范围为1~仪器光栅数。
        which: 滤光片轮的序号，范围为1~6。
        val : 滤光片有效波长起始位置。
        返回值：
        true: 成功读取滤光片有效波长起始位置。
        false: 单色仪ID、光栅号和滤光片轮序号至少一个有误，读取失败。"""
        self.spectrometer1.spec_get_filter_limit.argtypes = [
            ctypes.c_int, ctypes.c_int, ctypes.c_short, ctypes.POINTER(ctypes.c_double)]
        self.spectrometer1.spec_get_filter_limit.restype = ctypes.c_bool

        serial_no_3 = ctypes.c_int(id1)
        grating_no_1 = ctypes.c_int(grating_no)
        which_1 = ctypes.c_short(which)
        val_1 = ctypes.c_double(888.8)
        is_true = self.spectrometer1.spec_get_filter_limit(
            serial_no_3, grating_no_1, which_1, ctypes.byref(val_1))
        return is_true, val_1.value


# ---设置出入口相关---------------------------------------------


    def set_exit_port(self, front) -> bool:
        """设置出口摆镜
        front true:直出，false:侧出"""
        self.spectrometer1.spec_set_exit_port.argtypes = [
            ctypes.c_int, ctypes.c_bool]
        self.spectrometer1.spec_set_exit_port.restype = ctypes.c_bool

        # serial_no_2 = ctypes.c_int(id1)
        exit_port = ctypes.c_bool(front)

        if self.serial_no is not None:
            is_set = self.spectrometer1.spec_set_exit_port(
                self.serial_no, exit_port)
            # print('直出口设置：', is_set)
            return is_set
        else:
            return 'can not find device id'

    def get_exit_port(self,):
        """读取出口位置
        参数：
        id1 : 单色仪的ID。
        front : 出口位置标识符。可能值及其意义：
        true: 表示直出口。
        false: 表示侧出口。
        返回值：
        true: 成功读取出口位置。
        false: 读取失败。"""
        self.spectrometer1.spec_get_exit_port.argtypes = [
            ctypes.c_int, ctypes.POINTER(ctypes.c_bool)]
        self.spectrometer1.spec_get_exit_port.restype = ctypes.c_bool

        # serial_no_3 = ctypes.c_int(id1)
        front_1 = ctypes.c_bool(True)

        if self.serial_no is not None:
            is_true = self.spectrometer1.spec_get_exit_port(
                self.serial_no, ctypes.byref(front_1))
            return is_true, front_1.value
        else:
            return 'can not find device id'

    def set_side_exit_pos(self, id1: int, steps) -> bool:
        """设置侧出口位置电机步数
        参数：
        id1 : 单色仪的ID。
        step : 侧出口位置电机步数，范围为 -3200~0。
        返回值：
        true: 成功设置侧出口位置电机步数。
        false: 设置失败。"""
        self.spectrometer1.spec_set_side_exit_pos.argtypes = [
            ctypes.c_int, ctypes.c_int]
        self.spectrometer1.spec_set_side_exit_pos.restype = ctypes.c_bool

        serial_no_3 = ctypes.c_int(id1)
        steps_1 = ctypes.c_int(steps)
        is_true = self.spectrometer1.spec_set_side_exit_pos(
            serial_no_3, steps_1)

        return is_true

    def get_side_exit_pos(self, id1: int):
        """读取侧出口位置电机步数
        参数：
        id1 : 单色仪的ID。
        step : 侧出口位置电机步数，范围为 -3200~0。
        返回值：
        true: 成功读取侧出口位置电机步数。
        false: 读取失败。"""
        self.spectrometer1.spec_get_side_exit_pos.argtypes = [
            ctypes.c_int, ctypes.POINTER(ctypes.c_int)]
        self.spectrometer1.spec_get_side_exit_pos.restype = ctypes.c_bool

        serial_no_3 = ctypes.c_int(id1)
        steps_1 = ctypes.c_int(888)

        is_true = self.spectrometer1.spec_get_side_exit_pos(
            serial_no_3, ctypes.byref(steps_1))
        return is_true, steps_1.value

    def set_entrance_port(self, front) -> bool:
        """设置入口摆镜
        参数：
        id1 : 单色仪的ID。
        front : 入口位置标识符。可能值及其意义：
        true: 表示直入口。
        false: 表示侧入口。
        返回值：
        true: 成功设置入口位置。
        false: 设置失败。"""
        self.spectrometer1.spec_set_entrance_port.argtypes = [
            ctypes.c_int, ctypes.c_bool]
        self.spectrometer1.spec_set_entrance_port.restype = ctypes.c_bool

        # serial_no_2 = ctypes.c_int(id1)
        entrance_port = ctypes.c_bool(front)

        if self.serial_no is not None:
            is_set = self.spectrometer1.spec_set_entrance_port(
                self.serial_no, entrance_port)
            # print('直出口设置：', is_set)
            return is_set
        else:
            return 'can not get device id, try to open it'

    def get_entrance_port(self):
        """读取入口摆镜位置
        参数：
        id1 : 单色仪的ID。
        front : 入口位置标识符。可能值及其意义：
        true: 表示直入口。
        false: 表示侧入口。
        返回值：
        true: 成功读取入口位置。
        false: 读取失败"""
        self.spectrometer1.spec_get_entrance_port.argtypes = [
            ctypes.c_int, ctypes.POINTER(ctypes.c_bool)]
        self.spectrometer1.spec_get_entrance_port.restype = ctypes.c_bool

        # serial_no_3 = ctypes.c_int(id1)
        if self.serial_no is not None:
            entrance_port_1 = ctypes.c_bool(True)
            is_true = self.spectrometer1.spec_get_entrance_port(
                self.serial_no, ctypes.byref(entrance_port_1))
            return is_true, entrance_port_1.value
        else:
            return 'can not get device id, try to open it'

    def set_side_entrance_pos(self, id1: int, steps) -> bool:
        """设置侧入口位置电机步数
        参数：
        id1 : 单色仪的ID。
        step : 侧入口位置电机步数，范围为 -3200~0。
        返回值：
        true: 成功设置侧入口位置电机步数。
        false: 设置失败。"""
        self.spectrometer1.spec_set_side_entrance_pos.argtypes = [
            ctypes.c_int, ctypes.c_int]
        self.spectrometer1.spec_set_side_entrance_pos.restype = ctypes.c_bool

        serial_no_3 = ctypes.c_int(id1)
        steps_1 = ctypes.c_int(steps)
        is_true = self.spectrometer1.spec_set_side_entrance_pos(
            serial_no_3, steps_1)

        return is_true

    def spec_get_side_entrance_pos(self, id1: int):
        """读取侧入口位置电机步数
        参数：
        id1 : 单色仪的ID。
        step : 侧入口位置电机步数，范围为 -3200~0。
        返回值：
        true: 成功读取侧入口位置电机步数。
        false: 读取失败。"""
        self.spectrometer1.spec_get_side_entrance_pos.argtypes = [
            ctypes.c_int, ctypes.POINTER(ctypes.c_int)]
        self.spectrometer1.spec_get_side_entrance_pos.restype = ctypes.c_bool

        serial_no_3 = ctypes.c_int(id1)
        steps_1 = ctypes.c_int(888.8)

        is_true = self.spectrometer1.spec_get_side_entrance_pos(
            serial_no_3, ctypes.byref(steps_1))
        return is_true, steps_1.value


# ---设置自动狭缝相关---------------------------------------------

    def set_slit_factor(self, id1: int, val) -> bool:
        """设置自动狭缝带宽计算系数（系数与设备型号及光栅刻线数有关，默认2.3）
        参数：
        id1 : 单色仪的ID。
        val : 自动狭缝带宽计算系数。
        返回值：
        true: 成功设置自动狭缝带宽计算系数。
        false: 或者计算系数小于0，设置失败。"""
        self.spectrometer1.spec_set_slit_factor.argtypes = [
            ctypes.c_int, ctypes.c_float]
        self.spectrometer1.spec_set_slit_factor.restype = ctypes.c_bool

        serial_no_3 = ctypes.c_int(id1)
        val_1 = ctypes.c_float(val)

        is_true = self.spectrometer1.spec_set_slit_factor(
            serial_no_3, (val_1))
        return is_true

    def get_slit_factor(self, id1: int):
        """ 读取自动狭缝带宽计算系数（系数与设备型号及刻线数有关，默认2.3）
        参数：
        id1 : 单色仪的ID。
        val : 自动狭缝带宽计算系数。
        返回值：
        true: 成功读取自动狭缝带宽计算系数。
        false: 或者计算系数不存在，设置失败。"""
        self.spectrometer1.spec_get_slit_factor.argtypes = [
            ctypes.c_int, ctypes.POINTER(ctypes.c_float)]
        self.spectrometer1.spec_get_slit_factor.restype = ctypes.c_bool

        serial_no_3 = ctypes.c_int(id1)
        val_1 = ctypes.c_float(888.8)

        is_true = self.spectrometer1.spec_get_slit_factor(
            serial_no_3, ctypes.byref(val_1))
        return is_true, val_1.value

    def set_slit_width(self, id1: int, index, um) -> bool:
        """设置自动狭缝宽度，单位：um
        参数：
        id1 : 单色仪的ID。
        index : 自动狭缝号。参数可能值及其意义
        0–侧入  1–侧出  2–直出  3 -直入
        um : 狭缝宽度。单位为um。最小开启步距为 10um。
        返回值：
        true: 成功设置指定的自动狭缝宽度。
        false: 或者自动狭缝号超出范围，或者设置的狭缝宽度的数值不是10的正整数倍，导致设置自动狭缝宽度失败。"""
        self.spectrometer1.spec_set_slit_width.argtypes = [
            ctypes.c_int, ctypes.c_int, ctypes.c_int]
        self.spectrometer1.spec_set_slit_width.restype = ctypes.c_bool

        serial_no_1 = ctypes.c_int(id1)
        index_1 = ctypes.c_int(index)
        width_um = ctypes.c_int(um)

        is_set = self.spectrometer1.spec_set_slit_width(
            serial_no_1, index_1, width_um)
        return is_set

    def get_slit_width(self, id1: int, index):
        """读取指定的自动狭缝宽度
        参数：
        id1 : 单色仪的ID。
        index : 自动狭缝号。参数可能值及其意义
        0–侧入  1–侧出  2–直出  3 -直入
        um : 狭缝宽度。单位为um。
        返回值：
        true: 成功读取指定的自动狭缝宽度。
        false: 或者自动狭缝号超出范围，读取失败。"""
        self.spectrometer1.spec_get_slit_width.argtypes = [
            ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_int)]
        self.spectrometer1.spec_get_slit_width.restype = ctypes.c_bool

        serial_no_3 = ctypes.c_int(id1)
        index_1 = ctypes.c_int(index)
        um_1 = ctypes.c_int(88.8)

        is_true = self.spectrometer1.spec_get_slit_width(
            serial_no_3, index_1, ctypes.byref(um_1))
        return is_true, um_1.value

    def set_slit_bandpass(self, id1: int, index, nm) -> bool:
        """设置自动狭缝的带宽，单位：nm
        参数：
        id1 : 单色仪的ID。
        index : 自动狭缝号。参数可能值及其意义
        0–侧入  1–侧出  2–直出  3 -直入
        nm : 狭缝带宽。单位为nm。
        返回值：
        true: 成功设置指定的自动狭缝带宽。
        false: 或者自动狭缝号超出范围，设置自动狭缝带宽失败"""
        self.spectrometer1.spec_set_slit_bandpass.argtypes = [
            ctypes.c_int, ctypes.c_int, ctypes.c_float]
        self.spectrometer1.spec_set_slit_bandpass.restype = ctypes.c_bool

        serial_no_1 = ctypes.c_int(id1)
        index_1 = ctypes.c_int(index)
        width_nm = ctypes.c_float(nm)

        is_set = self.spectrometer1.spec_set_slit_bandpass(
            serial_no_1, index_1, width_nm)
        return is_set

    def get_slit_bandpass(self, id1: int, index):
        """读取指定的自动狭缝带宽
        参数：
        id1 : 单色仪的ID。
        index : 自动狭缝号。参数可能值及其意义
        0–侧入  1–侧出  2–直出  3 -直入
        nm : 狭缝带宽。单位为nm。
        返回值：
        true: 成功读取指定自动狭缝带宽。
        false: 或者自动狭缝号超出范围，读取失败。"""
        self.spectrometer1.spec_get_slit_bandpass.argtypes = [
            ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_float)]
        self.spectrometer1.spec_get_slit_bandpass.restype = ctypes.c_bool

        serial_no_3 = ctypes.c_int(id1)
        index_1 = ctypes.c_int(index)
        width_nm = ctypes.c_float(88.8)

        is_true = self.spectrometer1.spec_get_slit_bandpass(
            serial_no_3, index_1, ctypes.byref(width_nm))
        return is_true, width_nm.value

    def set_slit_zero_pos(self, id1: int, index, um) -> bool:
        """设置指定的自动狭缝零点位置
        参数：
        id1 : 单色仪的ID。
        index : 自动狭缝号。参数可能值及其意义
        0–侧入  1–侧出  2–直出  3 -直入
        nm : 狭缝零点位置。单位为um，范围为 -100~100 um。
        返回值：
        true: 成功设置指定的自动狭缝零点位置。
        false: 或者自动狭缝号超出范围，设置失败。"""
        self.spectrometer1.spec_set_slit_zero_pos.argtypes = [
            ctypes.c_int, ctypes.c_int, ctypes.c_int]
        self.spectrometer1.spec_set_slit_zero_pos.restype = ctypes.c_bool

        serial_no_3 = ctypes.c_int(id1)
        index_1 = ctypes.c_int(index)
        um_1 = ctypes.c_int(um)

        is_true = self.spectrometer1.spec_set_slit_zero_pos(
            serial_no_3, index_1, um_1)
        return is_true

    def get_slit_zero_pos(self, id1: int, index):
        """读取指定的自动狭缝零点位置
        参数：
        id1 : 单色仪的ID。
        index : 自动狭缝号。参数可能值及其意义
        0–侧入  1–侧出  2–直出  3 -直入
        um : 狭缝零点位置。单位为um，范围为 -100~100 um。
        返回值：
        true: 成功读取指定的自动狭缝零点位置。
        false: 或者自动狭缝号超出范围，读取失败。"""
        self.spectrometer1.spec_get_slit_zero_pos.argtypes = [
            ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_int)]
        self.spectrometer1.spec_get_slit_zero_pos.restype = ctypes.c_bool

        serial_no_3 = ctypes.c_int(id1)
        index_1 = ctypes.c_int(index)
        um_1 = ctypes.c_int(88.8)

        is_true = self.spectrometer1.spec_get_slit_zero_pos(
            serial_no_3, index_1, ctypes.byref(um_1))
        return is_true, um_1.value

    def set_slit_home(self, id1: int, index) -> bool:
        """设置自动狭缝归零，即到最小保护宽度
        参数：
        id1 : 单色仪的ID。
        index : 自动狭缝位置序号。参数可能值及其意义
        0–侧入  1–侧出  2–直出  3 -直入
        返回值：
        true: 成功完成自动狭缝定位。
        false: 或者自动狭缝位置序号超出范围，定位失败。"""
        self.spectrometer1.spec_set_slit_home.argtypes = [
            ctypes.c_int, ctypes.c_int]
        self.spectrometer1.spec_set_slit_home.restype = ctypes.c_bool

        serial_no_1 = ctypes.c_int(id1)
        auto_slit_no = ctypes.c_int(index)

        is_set = self.spectrometer1.spec_set_slit_home(
            serial_no_1, auto_slit_no)
        return is_set

    def set_slit_model(self, id1: int, model) -> bool:
        """设置自动狭缝型号
        参数：
        id1 : 单色仪的ID。
        model : 自动狭缝型号。可能值为SLIT/SLIT-I24/SR-SLIT。
        返回值：
        true: 成功设置自动狭缝型号。
        false: 设置失败。"""
        self.spectrometer1.spec_set_slit_model.argtypes = [
            ctypes.c_int, ctypes.c_char_p]
        self.spectrometer1.spec_set_slit_model.restype = ctypes.c_bool

        serial_no_3 = ctypes.c_int(id1)
        model_1 = model.encode()
        model_2 = ctypes.c_char_p(model_1)
        is_true = self.spectrometer1.spec_set_slit_model(
            serial_no_3, model_2)
        return is_true

    def get_slit_model(self, id1: int):
        """读取自动狭缝型号
        参数：
        id1 : 单色仪的ID。
        model : 自动狭缝型号。可能值为SLIT/SLIT-I24/SR-SLIT。
        返回值：
        true: 成功读取自动狭缝型号。
        false: 读取失败。"""
        self.spectrometer1.spec_get_slit_model.argtypes = [
            ctypes.c_int, ctypes.c_char_p]
        self.spectrometer1.spec_get_slit_model.restype = ctypes.c_bool

        serial_no_3 = ctypes.c_int(id1)
        model_1 = (ctypes.c_char*10)()
        is_true = self.spectrometer1.spec_get_slit_model(
            serial_no_3, model_1)
        return is_true, model_1.value


# ---电机设置相关---------------------------------------------


    def set_motor_steps(self, id1: int, index, steps) -> bool:
        """设置步进电机绝对移动步数
        参数：
        id1 : 单色仪的ID。
        index : 步进电机的序号，范围为 3~9。
        steps : 移动步数。
        返回值：
        true: 成功设置步进电机绝对移动步数。
        false: 设置失败。"""
        self.spectrometer1.spec_set_motor_steps.argtypes = [
            ctypes.c_int, ctypes.c_int, ctypes.c_long]
        self.spectrometer1.spec_set_motor_steps.restype = ctypes.c_bool

        serial_no_3 = ctypes.c_int(id1)
        index_1 = ctypes.c_int(index)
        steps_1 = ctypes.c_long(steps)

        is_true = self.spectrometer1.spec_set_motor_steps(
            serial_no_3, index_1, steps_1)
        return is_true

    def get_motor_steps(self, id1: int, index):
        """读取步进电机绝对移动步数
        参数：
        id1 : 单色仪的ID。
        index : 步进电机的序号，范围为2~13。
        steps : 移动步数。
        返回值：
        true: 成功设置步进电机绝对移动步数。
        false: 设置失败。"""
        self.spectrometer1.spec_get_motor_steps.argtypes = [
            ctypes.c_int, ctypes.POINTER(ctypes.c_int)]
        self.spectrometer1.spec_get_motor_steps.restype = ctypes.c_bool

        serial_no_3 = ctypes.c_int(id1)
        index_1 = ctypes.c_int(index)
        steps_1 = ctypes.c_long(888)

        is_true = self.spectrometer1.spec_get_motor_steps(
            serial_no_3, index_1, ctypes.byref(steps_1))
        return is_true, steps_1.value

    def set_motor_home(self, id1: int, index) -> bool:
        """将步进电机重新定位，使其回到机械零点
        参数：
        id1 : 单色仪的ID。
        index : 步进电机的序号。
        返回值：
        true: 成功将步进电机重新定位，使其回到机械零点。
        false: 重新定位失败。"""
        self.spectrometer1.spec_set_motor_home.argtypes = [
            ctypes.c_int, ctypes.c_int]
        self.spectrometer1.spec_set_motor_home.restype = ctypes.c_bool

        serial_no_3 = ctypes.c_int(id1)
        index_1 = ctypes.c_int(index)
        is_true = self.spectrometer1.spec_set_motor_home(
            serial_no_3, index_1)
        return is_true

    def set_motor_speed(self, id1: int, index, speed) -> bool:
        """设置步进电机移动速度
        参数：
        id1 : 单色仪的ID。
        index : 步进电机的序号，范围为 3~9。
        speed : 步进电机移动速度，范围为10~2000 PPS。谱仪不对此参数进行保存。
        返回值：
        true: 成功设置步进电机移动速度。
        false: 设置电机移动速度失败。"""
        self.spectrometer1.spec_set_motor_speed.argtypes = [
            ctypes.c_int, ctypes.c_int,  ctypes.c_int]
        self.spectrometer1.spec_set_motor_speed.restype = ctypes.c_bool

        serial_no_3 = ctypes.c_int(id1)
        index_1 = ctypes.c_int(index)
        speed_1 = ctypes.c_int(speed)

        is_true = self.spectrometer1.spec_set_motor_speed(
            serial_no_3, index_1, speed_1)
        return is_true

    def get_motor_speed(self, id1: int, index):
        """读取步进电机移动速度
        参数：
        id1 : 单色仪的ID。
        index : 步进电机的序号。
        speed : 步进电机移动速度，范围为10~2000 PPS。谱仪不对此参数进行保存。
        返回值：
        true: 成功读取步进电机移动速度。
        false: 读取电机移动速度失败。"""
        self.spectrometer1.spec_get_motor_speed.argtypes = [
            ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_int)]
        self.spectrometer1.spec_get_motor_speed.restype = ctypes.c_bool

        serial_no_3 = ctypes.c_int(id1)
        index_1 = ctypes.c_int(index)
        speed_1 = ctypes.c_int(888.8)

        is_true = self.spectrometer1.spec_get_motor_speed(
            serial_no_3, index_1, ctypes.byref(speed_1))
        return is_true, speed_1.value

    def set_motor_home_dir(self, id1: int, index, dir11) -> bool:
        """设置步进电机定位方向
        参数：
        id1 : 单色仪的ID。
        index : 步进电机的序号，范围为 3~9。
        dir : 步进电机定位方向。可能值及其意义：
        1: 电机往正方向运转去执行定位动作。
        0: 电机往反方向运转去执行定位动作。
        返回值：
        true: 成功设置步进电机定位方向。
        false: 设置步进电机定位方向失败。"""
        self.spectrometer1.spec_set_motor_home_dir.argtypes = [
            ctypes.c_int, ctypes.c_int, ctypes.c_int]
        self.spectrometer1.spec_set_motor_home_dir.restype = ctypes.c_bool

        serial_no_3 = ctypes.c_int(id1)
        index_1 = ctypes.c_int(index)
        dir_1 = ctypes.c_int(dir11)

        is_true = self.spectrometer1.spec_set_motor_home_dir(
            serial_no_3, index_1, dir_1)
        return is_true

    def get_motor_home_dir(self, id1: int, index):
        """读取步进电机定位方向
        参数：
        id1 : 单色仪的ID。
        index : 步进电机的序号。
        dir : 步进电机定位方向。可能值及其意义：
        1: 电机往正方向运转去执行定位动作。
        0: 电机往反方向运转去执行定位动作。
        返回值：
        true: 成功读取步进电机定位方向。
        false: 读取步进电机定位方向失败。"""
        self.spectrometer1.spec_get_motor_home_dir.argtypes = [
            ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_int)]
        self.spectrometer1.spec_get_motor_home_dir.restype = ctypes.c_bool

        serial_no_3 = ctypes.c_int(id1)
        index_1 = ctypes.c_int(index)
        dir_1 = ctypes.c_int(0)

        is_true = self.spectrometer1.spec_get_motor_home_dir(
            serial_no_3, index_1, ctypes.byref(dir_1))
        return is_true, dir_1.value

    def set_motor_total_steps(self, id1: int, index, total) -> bool:
        """设置步进电机总步数
        参数：
        id1 : 单色仪的ID。
        index : 步进电机的序号，范围为2~13。
        total : 步进电机总步数，范围为0~2147483647。
        返回值：
        true: 成功设置步进电机总步数。
        false: 设置步进电机总步数失败。"""
        self.spectrometer1.spec_set_motor_total_steps.argtypes = [
            ctypes.c_int, ctypes.c_int, ctypes.c_long]
        self.spectrometer1.spec_set_motor_total_steps.restype = ctypes.c_bool

        serial_no_3 = ctypes.c_int(id1)
        index_1 = ctypes.c_int(index)
        total_1 = ctypes.c_long(total)
        is_true = self.spectrometer1.spec_set_motor_total_steps(
            serial_no_3, index_1, total_1)
        return is_true

    def get_motor_total_steps(self, id1: int, index):
        """读取步进电机总步数
        参数：
        id1 : 单色仪的ID。
        index : 步进电机的序号，范围为2~13。
        total : 步进电机总步数，范围为0~2147483647。
        返回值：
        true: 成功设置步进电机总步数。
        false: 设置步进电机总步数失败。"""
        self.spectrometer1.spec_get_motor_total_steps.argtypes = [
            ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_long)]
        self.spectrometer1.spec_get_motor_total_steps.restype = ctypes.c_bool

        serial_no_3 = ctypes.c_int(id1)
        index_1 = ctypes.c_int(index)
        total_1 = ctypes.c_long(8888)

        is_true = self.spectrometer1.spec_get_motor_total_steps(
            serial_no_3, index_1, ctypes.byref(total_1))
        return is_true, total_1.value


# ---设置快门相关---------------------------------------------


    def set_shutter_status(self, id1: int, port, status) -> bool:
        """设置快门的开关
        参数：
        id1 : 单色仪的ID。
        port : 快门安装位置。可能值及其意义：
        0: 侧入。			1: 直入。
        2: 侧出。			3: 直出。
        status : 快门状态。可能值及其意义：
        true: 开。			false: 关。
        返回值：
        true: 成功设置快门开关。
        false: 或者快门入口类型有误，设置快门开关失败。"""
        self.spectrometer1.spec_set_shutter_status.argtypes = [
            ctypes.c_int, ctypes.c_int, ctypes.c_bool]
        self.spectrometer1.spec_set_shutter_status.restype = ctypes.c_bool

        serial_no_2 = ctypes.c_int(id1)
        port2 = ctypes.c_int(port)
        status_2 = ctypes.c_bool(status)

        is_set = self.spectrometer1.spec_set_shutter_status(
            serial_no_2, port2, status_2)
        return is_set

    def get_shutter_status(self, id1: int, port):
        """读取快门开关状态
        参数：
        id1 : 单色仪的ID。
        port : 快门安装位置。可能值及其意义：
        0: 侧入。			1: 直入。
        2: 侧出。			3: 直出。
        status : 快门状态。可能值及其意义：
        true: 开。			false: 关。
        返回值：
        true: 成功读取快门开关。
        false: 或者快门入口类型有误，读取快门开关状态失败。"""
        self.spectrometer1.spec_get_shutter_status.argtypes = [
            ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_bool)]
        self.spectrometer1.spec_get_shutter_status.restype = ctypes.c_bool

        serial_no_3 = ctypes.c_int(id1)
        port2 = ctypes.c_int(port)
        status_2 = ctypes.c_bool(1)

        is_true = self.spectrometer1.spec_get_shutter_status(
            serial_no_3, port2, ctypes.byref(status_2))
        return is_true, status_2.value


# ---相关附件查询------------------------------------------------------------


    def is_setup_filter(self, id1: int, index):
        """查询是否已安装滤光片轮
        参数：
        id1 : 单色仪的ID。
        index: 0-外置滤光片轮, 1-内置滤光片轮。
        setup : 滤光片轮的安装状态。可能值及其意义：
        true: 已安装。			false: 未安装。
        返回值：
        true: 成功查询到滤光片轮安装状态。
        false: 查询失败。"""

        self.spectrometer1.spec_is_setup_filter.argtypes = [
            ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_bool)]
        self.spectrometer1.spec_is_setup_filter.restype = ctypes.c_bool

        serial_no_3 = ctypes.c_int(id1)
        index_1 = ctypes.c_int(index)
        setup_1 = ctypes.c_bool(1)

        is_true = self.spectrometer1.spec_is_setup_filter(
            serial_no_3, index_1, ctypes.byref(setup_1))
        return is_true, setup_1.value

    def setup_filter(self, id1: int, index, setup):
        """设置是否安装滤光片轮，仅支持侧入安装
        参数：
        id1 : 单色仪的ID。
        index: 0-外置滤光片轮, 1-内置滤光片轮。
        setup : 滤光片轮的安装选项。可能值及其意义：
        true: 确认安装。			false: 取消安装。
        返回值：
        true: 成功设置滤光片轮的安装选项。
        false: 设置失败。"""

        self.spectrometer1.spec_setup_filter.argtypes = [
            ctypes.c_int, ctypes.c_int, ctypes.c_bool]
        self.spectrometer1.spec_setup_filter.restype = ctypes.c_bool

        serial_no_3 = ctypes.c_int(id1)
        index_1 = ctypes.c_int(index)
        setup_1 = ctypes.c_bool(setup)

        is_true = self.spectrometer1.spec_setup_filter(
            serial_no_3, index_1, ctypes.byref(setup_1))
        return is_true, setup_1.value

    def is_setup_mirror(self, id1: int, index):
        """查询是否已安装摆镜
        参数：
        id1 : 单色仪的ID。
        index : 摆镜的安装位置。可能值及其意义：
        0: 出口。			    1: 入口。
        setup : 摆镜的安装状态。可能值及其意义：
        true: 已安装。			false: 未安装。
        返回值：
        true: 成功查询到摆镜安装状态。
        false: 查询失败。"""
        self.spectrometer1.spec_is_setup_mirror.argtypes = [
            ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_bool)]
        self.spectrometer1.spec_is_setup_mirror.restype = ctypes.c_bool

        serial_no_3 = ctypes.c_int(id1)
        index_1 = ctypes.c_int(index)
        setup_1 = ctypes.c_bool(1)

        is_true = self.spectrometer1.spec_is_setup_mirror(
            serial_no_3, index_1, ctypes.byref(setup_1))
        return is_true, setup_1.value

    def setup_mirror(self, id1: int, index, setup) -> bool:
        """设置是否安装摆镜
        参数：
        id1 : 单色仪的ID。
        index : 摆镜的安装位置。可能值及其意义：
        0: 出口。			    1: 入口。
        setup : 摆镜的安装选项。可能值及其意义：
        true: 确认安装。		false: 取消安装。
        返回值：
        true: 成功设置摆镜安装选项。
        false: 设置失败。"""
        self.spectrometer1.spec_setup_mirror.argtypes = [
            ctypes.c_int, ctypes.c_int, ctypes.c_bool]
        self.spectrometer1.spec_setup_mirror.restype = ctypes.c_bool

        serial_no_3 = ctypes.c_int(id1)
        index_1 = ctypes.c_int(index)
        setup_1 = ctypes.c_bool(setup)

        is_true = self.spectrometer1.spec_setup_mirror(
            serial_no_3, index_1, setup_1)
        return is_true

    def is_setup_slit(self, id1: int, index):
        """查询是否已安装狭缝
        参数：
        id1 : 单色仪的ID。
        index : 狭缝的安装位置。可能值及其意义：
        0: 侧入。			    1: 侧出。
        2: 直出。			    3: 直入。
        setup : 狭缝的安装状态。可能值及其意义：
        true: 已安装。			false: 未安装。
        返回值：
        true: 成功查询到狭缝安装状态。
        false: 查询失败。"""
        self.spectrometer1.spec_is_setup_slit.argtypes = [
            ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_bool)]
        self.spectrometer1.spec_is_setup_slit.restype = ctypes.c_bool

        serial_no_3 = ctypes.c_int(id1)
        index_1 = ctypes.c_int(index)
        setup_1 = ctypes.c_bool(1)

        is_true = self.spectrometer1.spec_is_setup_slit(
            serial_no_3, index_1, ctypes.byref(setup_1))
        return is_true, setup_1.value

    def setup_slit(self, id1: int, index, setup) -> bool:
        """设置是否安装狭缝
        参数：
        id1 : 单色仪的ID。
        index : 狭缝的安装位置。可能值及其意义：
        0: 侧入。			    1: 侧出。
        2: 直出。			    3: 直入。
        setup : 狭缝的安装选项。可能值及其意义：
        true: 确认安装。		false: 取消安装。
        返回值：
        true: 成功设置狭缝安装选项。
        false: 设置失败。"""

        self.spectrometer1.spec_setup_slit.argtypes = [
            ctypes.c_int,  ctypes.c_int, ctypes.c_bool]
        self.spectrometer1.spec_setup_slit.restype = ctypes.c_bool

        serial_no_3 = ctypes.c_int(id1)
        index_1 = ctypes.c_int(index)
        setup_1 = ctypes.c_bool(setup)

        is_true = self.spectrometer1.spec_setup_slit(
            serial_no_3, index_1, setup_1)
        return is_true

    def is_setup_shutter(self, id1: int, index):
        """查询是否已安装快门
        参数：
        id1 : 单色仪的ID。
        index : 快门的安装位置。可能值及其意义：
        0: 侧入。			    1: 直入。
        2: 侧出。			    3: 直出。
        setup : 快门的安装状态。可能值及其意义：
        true: 已安装。			false: 未安装。
        返回值：
        true: 成功查询到快门安装状态。
        false: 查询失败。"""

        self.spectrometer1.spec_is_setup_shutter.argtypes = [
            ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_bool)]
        self.spectrometer1.spec_is_setup_shutter.restype = ctypes.c_bool

        serial_no_3 = ctypes.c_int(id1)
        index_1 = ctypes.c_int(index)
        setup_1 = ctypes.c_bool(1)

        is_true = self.spectrometer1.spec_is_setup_shutter(
            serial_no_3, index_1, ctypes.byref(setup_1))

        return is_true, setup_1.value

    def setup_shutter(self, id1: int, index, setup) -> bool:
        """设置是否安装快门
        参数：
        id1 : 单色仪的ID。
        index : 快门的安装位置。可能值及其意义：
        0: 侧入。			    1: 直入。
        2: 侧出。			    3: 直出。
        setup : 快门的安装选项。可能值及其意义：
        true: 确认安装。		false: 取消安装。
        返回值：
        true: 成功设置快门安装选项。
        false: 设置失败。"""

        self.spectrometer1.spec_setup_shutter.argtypes = [
            ctypes.c_int, ctypes.c_int, ctypes.c_bool]
        self.spectrometer1.spec_setup_shutter.restype = ctypes.c_bool

        serial_no_3 = ctypes.c_int(id1)
        index_1 = ctypes.c_int(index)
        setup_1 = ctypes.c_bool(setup)

        is_true = self.spectrometer1.spec_setup_shutter(
            serial_no_3, index_1, setup_1)
        return is_true

# ---校正系数相关-------------------------------------
    def set_correct_params(self, id1: int):
        # 缺省
        return None

    def get_correct_params(self, id1: int, turret, grating_no, code) -> bool:
        """获取单个校正系数
        id1 : 单色仪的ID。
        turret: 塔台序号，范围为1~3。
        grating : 光栅序号，范围为1~3。
        code : 校正系数标识符，范围为0~16。可能值及其意义：
        Value					 V3.4及以上 V3.4以下
        0: 谱仪焦距				float		   float
        1: 谱仪内置角				float		   float
        2: 焦面倾斜角				float		   float
        3: 光栅校正系数1			double	   float
        4: 光栅校正系数2 			double	   float
        5: 光栅校正系数3 			double	   float
        6: 光栅校正系数4 			double	   float
        7: 光栅校正系数5 			double	   float
        8: 余弦校正系数——振幅	double	   float
        9: 余弦校正系数——相位	double	   float
        10: 余弦校正系数——频率	double	   float
        11: 光栅起始电机步数		int		   int
        12: 光栅偏置电机步数		short	   int
        13: 光栅刻线				double	   float
        14: 光栅闪耀波长			double	   -
        15: 直出偏置				short	   short
        16: 侧出偏置				short	   short
        param : 校正系数。"""
        self.spectrometer1.spec_get_correct_params.argtypes = [
            ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_double)]
        self.spectrometer1.spec_get_correct_params.restype = ctypes.c_bool

        serial_no_4 = ctypes.c_int(id1)
        turret_1 = ctypes.c_int(turret)
        grating_no = ctypes.c_int(grating_no)
        code2 = ctypes.c_int(code)

        if code == 0 or code == 1 or code == 2:
            param1 = ctypes.c_float(666.0)
        elif code in (3, 4, 5, 6, 7, 8, 9, 10, 13, 14):
            param1 = ctypes.c_double(666.0)
        elif code == 11:
            param1 = ctypes.c_int(666.0)
        elif code == 12 or code == 15 or code == 16:
            param1 = ctypes.c_short(666.0)
        else:
            param1 = ctypes.c_float(666.0)

        is_true = self.spectrometer1.spec_get_correct_params(
            serial_no_4, turret_1, grating_no, code2, ctypes.byref(param1))
        # print('校正系数——参数1：{0}, 是否正确读取：{1}'.format(param1.value,is_true))
        return is_true, param1.value

    def get_all_params(self, id1: int, grating_no):
        """获取光栅的所有的校正系数"""
        params = []
        for code in range(17):
            kk, param = self.get_correct_params(id1, grating_no, code)
            params.append(param)
        return params

    def wave_to_step(self, id1: int, wave):
        """计算目标中心波长的绝对电机步数"""
        self.spectrometer1.spec_wave_to_step.argtypes = [
            ctypes.c_int, ctypes.c_float]
        self.spectrometer1.spec_wave_to_step.restype = ctypes.c_float

        serial_no_3 = ctypes.c_int(id1)
        wave1 = ctypes.c_float(wave)
        # grating_no =  ctypes.POINTER(tt3)
        steps_to_go = self.spectrometer1.spec_wave_to_step(
            serial_no_3, wave1)
        return steps_to_go

    def pixels_to_waves(self, id1: int, turret, grating, center_wave, width, count, bin1):
        """ 根据校正系数将x轴像素坐标换算为波长
        id谱仪序列号，width：CCD单像素宽度，单位um
        center_wave当前的中心波长，单位nm
        count CCD总像素数
        返回，波长数组"""
        self.spectrometer1.spec_pixels_to_waves.restype = ctypes.c_bool

        serial_no_3 = ctypes.c_int(id1)
        turret_1 = ctypes.c_int(turret)
        grating1 = ctypes.c_int(grating)
        width2 = ctypes.c_int(width)
        center_wave2 = ctypes.c_float(center_wave)
        count2 = ctypes.c_int(count)
        bin_1 = ctypes.c_int(bin1)
        data = (ctypes.c_float*count)()
        self.spectrometer1.spec_pixels_to_waves(
            serial_no_3, turret_1, grating1,  center_wave2, width2, count2, bin_1, ctypes.pointer(data))
        return data


# -------附件初始设置相关------------------------------------------------------------------

    def set_init_peripherals(self, id1: int, peripherals) -> bool:
        """固件版本号3.4及以上可用
        设置上电时需要初始化的外设
        参数：
        id1 : 单色仪的ID。
        peripherals: 外设代码，可能值及其意义，可组合。
        0x0001 滤光片轮
        0x0002 出口摆镜
        0x0004 侧入自动狭缝
        0x0008 侧出自动狭缝
        0x0010 直出自动狭缝
        0x0020 直入自动狭缝
        0x0040 入口摆镜
        0x0080 内置滤光片轮(9号电机)
        0x0100 快门1
        0x0200 快门2
        0x0400 聚焦镜, 仅支持HiperS-320i型谱仪
        0x0800 保留, 仅支持HiperS-320i型谱仪
        0x1000 侧入口光阑, 仅支持HiperS-320i型谱仪
        0x2000 直入口光阑, 仅支持HiperS-320i型谱仪
        返回值：
        表示是否成功读取。可能值及其意义：
        true: 成功。
        false: 失败。"""
        self.spectrometer1.spec_set_init_peripherals.argtypes = [
            ctypes.c_int, (ctypes.c_ushort)]
        self.spectrometer1.spec_set_init_peripherals.restype = ctypes.c_bool

        serial_no_3 = ctypes.c_int(id1)
        peripherals_1 = ctypes.c_ushort(peripherals)
        is_true = self.spectrometer1.spec_set_init_peripherals(
            serial_no_3, peripherals_1)
        return is_true

    def get_init_peripherals(self, id1: int) -> bool:
        """固件版本号3.4及以上可用
        读取上电时需要初始化的外设
        id1 : 单色仪的ID。
        peripherals: 外设代码，可能值及其意义，可组合。
        0x0001 滤光片轮
        0x0002 出口摆镜
        0x0004 侧入自动狭缝
        0x0008 侧出自动狭缝
        0x0010 直出自动狭缝
        0x0020 直入自动狭缝
        0x0040 入口摆镜
        0x0080 内置滤光片轮(9号电机)
        0x0100 快门1
        0x0200 快门2
        0x0400 聚焦镜, 仅支持HiperS-320i型谱仪
        0x0800 保留, 仅支持HiperS-320i型谱仪
        0x1000 侧入口光阑, 仅支持HiperS-320i型谱仪
        0x2000 直入口光阑, 仅支持HiperS-320i型谱仪
        返回值：
        表示是否成功读取。可能值及其意义：
        true: 成功。
        false: 失败。"""
        self.spectrometer1.spec_get_init_peripherals.argtypes = [
            ctypes.c_int, ctypes.POINTER(ctypes.c_ushort)]
        self.spectrometer1.spec_get_init_peripherals.restype = ctypes.c_bool

        serial_no_3 = ctypes.c_int(id1)
        peripherals_1 = ctypes.c_ushort(0x0001)

        is_true = self.spectrometer1.spec_get_init_peripherals(
            serial_no_3, ctypes.byref(peripherals_1))
        return is_true, peripherals_1.value

    def set_peripherals_init_pos(self, id1: int, peripheral, pos) -> bool:
        """固件版本号3.4及以上可用
        设置上电时外设初始化位置
        参数：
        id1 : 单色仪的ID。
        peripherals: 外设代码，不可组合。
        0x0001 滤光片轮
        0x0002 出口摆镜
        0x0004 侧入自动狭缝
        0x0008 侧出自动狭缝
        0x0010 直出自动狭缝
        0x0020 直入自动狭缝
        0x0040 入口摆镜
        0x0080 9号电机
        0x0100 快门1
        0x0200 快门2
        0x0400 聚焦镜, 仅支持HiperS-320i型谱仪
        0x0800 保留, 仅支持HiperS-320i型谱仪
        0x1000 侧入口光阑, 仅支持HiperS-320i型谱仪
        0x2000 直入口光阑, 仅支持HiperS-320i型谱仪
        Pos: 0 - 归零位置，1 - 上次关机时位置
        返回值：
        表示是否成功设置。可能值及其意义：
        true: 成功。
        false: 失败。"""
        self.spectrometer1.spec_set_peripherals_init_pos.argtypes = [
            ctypes.c_int, ctypes.c_ushort, ctypes.c_ubyte]
        self.spectrometer1.spec_set_peripherals_init_pos.restype = ctypes.c_bool

        serial_no_3 = ctypes.c_int(id1)
        peripheral_1 = ctypes.c_ushort(peripheral)
        pos_1 = ctypes.c_ubyte(pos)
        is_true = self.spectrometer1.spec_set_peripherals_init_pos(
            serial_no_3, peripheral_1, pos_1)
        return is_true

    def get_peripherals_init_pos(self, id1: int, peripheral) -> bool:
        """固件版本号3.4及以上可用
        设置上电时外设初始化位置
        参数：
        id1 : 单色仪的ID。
        peripherals: 外设代码，不可组合。
        0x0001 滤光片轮
        0x0002 出口摆镜
        0x0004 侧入自动狭缝
        0x0008 侧出自动狭缝
        0x0010 直出自动狭缝
        0x0020 直入自动狭缝
        0x0040 入口摆镜
        0x0080 9号电机
        0x0100 快门1
        0x0200 快门2
        0x0400 聚焦镜, 仅支持HiperS-320i型谱仪
        0x0800 保留, 仅支持HiperS-320i型谱仪
        0x1000 侧入口光阑, 仅支持HiperS-320i型谱仪
        0x2000 直入口光阑, 仅支持HiperS-320i型谱仪
        Pos: 0 - 归零位置，1 - 上次关机时位置
        返回值：
        表示是否成功设置。可能值及其意义：
        true: 成功。
        false: 失败。"""
        self.spectrometer1.spec_get_peripherals_init_pos.argtypes = [
            ctypes.c_int, ctypes.c_ushort, ctypes.POINTER(ctypes.c_ubyte)]
        self.spectrometer1.spec_get_peripherals_init_pos.restype = ctypes.c_bool

        serial_no_3 = ctypes.c_int(id1)
        peripheral_1 = ctypes.c_ushort(peripheral)
        pos_1 = ctypes.c_ubyte(0)
        is_true = self.spectrometer1.spec_get_peripherals_init_pos(
            serial_no_3, peripheral_1, ctypes.byref(pos_1))
        return is_true, pos_1.value


# -------触发控制相关------------------------------------------------------------------


    def set_trig_out_interval(self, id1: int, grating_no):
        # 缺省
        pass

    def spec_get_trig_out_interval(self, id1: int):
        # 缺省
        pass

    def set_trig_mode(self, id1: int, grating_no):
        # 缺省
        pass

    def set_trig_in_interval(self, id1: int, grating_no):
        # 缺省
        pass

    def get_trig_in_interval(self, id1: int):
        # 缺省
        pass

# -------内置步进扫描方式------------------------------------------------------------------

    def range_move(self, id1: int, from_nm, to_nm, step_nm, nm_s) -> bool:
        """固件版本号3.4及以上可用
        设置单色仪范围移动，每移动设置间隔，向外发送一个脉冲信号
        id1 :  单色仪的ID。
        from_nm: 移动起始波长，单位nm。
        to_nm: 移动波长间隔，单位nm。
        step_nm: 移动终止波长，单位nm。
        nm_s: 移动速度，单位nm/s，小于等于spec_get_move_speed读取的速度值.
        返回值：
        表示是否成功设置。可能值及其意义：
        true: 成功。
        false: 失败"""
        self.spectrometer1.spec_range_move.argtypes = [
            ctypes.c_int, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_int]
        self.spectrometer1.spec_range_move.restype = ctypes.c_bool

        serial_no_3 = ctypes.c_int(id1)
        from_nm_1 = ctypes.c_float(from_nm)
        to_nm_1 = ctypes.c_float(to_nm)
        step_nm_1 = ctypes.c_float(step_nm)
        nm_s_1 = ctypes.c_int(nm_s)
        is_true = self.spectrometer1.spec_range_move(
            serial_no_3, from_nm_1, to_nm_1, step_nm_1, nm_s_1)
        return is_true

    def spec_range_move2(self, id1: int, from_nm, to_nm, step_nm, delay_ms) -> bool:
        """固件版本号3.4及以上可用
        设置单色仪范围移动，每移动设置间隔后，等待设置延迟(毫秒)，再向外发送一个脉冲信号。
        参数：
        id1 :  单色仪的ID。
        from_nm: 移动起始波长，单位nm。
        to_nm: 移动波长间隔，单位nm。
        step_nm: 移动终止波长，单位nm。
        delay_ms: 单步移动完成后，延迟时间，单位ms
        返回值：
        表示是否成功设置。可能值及其意义：
        true: 成功。
        false: 失败"""
        self.spectrometer1.spec_range_move2.argtypes = [
            ctypes.c_int, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_int]
        self.spectrometer1.spec_range_move2.restype = ctypes.c_bool

        serial_no_3 = ctypes.c_int(id1)
        from_nm_1 = ctypes.c_float(from_nm)
        to_nm_1 = ctypes.c_float(to_nm)
        step_nm_1 = ctypes.c_float(step_nm)
        delay_ms_1 = ctypes.c_int(delay_ms)
        is_true = self.spectrometer1.spec_range_move2(
            serial_no_3, from_nm_1, to_nm_1, step_nm_1, delay_ms_1)
        return is_true


# -------CCD模式设置------------------------------------------------------------------

    # 在固件版本号3.4之前版本，CCD模式下的当前光栅位置中心波长记录在电脑内存中，软件重新启动之后，
    # 无法读取当前光栅位置的CCD模式中心波长；在固件版本号3.4及以上版本，CCD模式下的当前光栅位置的
    # 中心波长记录在光谱仪底层，可以实时读取当前光栅位置的CCD模式中心波长。

    def set_ccd_mode(self, id1: int, mode) -> bool:
        """设置谱仪当前搭配使用的数采为CCD，固件版本号3.4及以上可用
        参数：
        id1 :  单色仪的ID。
        ccd_mode: 是否为搭配ccd使用模式。
        返回值：
        表示是否成功设置。可能值及其意义：
        true: 成功。
        false: 失败。"""
        self.spectrometer1.spec_set_ccd_mode.argtypes = [
            ctypes.c_int, ctypes.c_bool]
        self.spectrometer1.spec_set_ccd_mode.restype = ctypes.c_bool

        serial_no_3 = ctypes.c_int(id1)
        ccd_mode = ctypes.c_bool(mode)
        is_true = self.spectrometer1.spec_set_ccd_mode(
            serial_no_3, ccd_mode)
        return is_true

    def get_ccd_mode(self, id1: int) -> bool:
        """读取谱仪当前搭配使用的数采是否为CCD
        id1 :  单色仪的ID
        返回值：
        true: 搭配ccd使用模式
        false: 常规模式"""
        self.spectrometer1.spec_get_ccd_mode.argtypes = [
            ctypes.c_int]
        self.spectrometer1.spec_get_ccd_mode.restype = ctypes.c_bool

        serial_no_3 = ctypes.c_int(id1)
        is_true = self.spectrometer1.spec_get_ccd_mode(serial_no_3)
        return is_true


# -------接谱相关------------------------------------------------------------------


    def init_spectral_splice(self, id1: int, pixel_width, pixel_count, bin_x, from1, to1, refwave, op) -> bool:
        """初始化接谱参数，计算出接谱需要的中心波长
        [IN] id1 :  单色仪的ID
        [IN] pixel_width: 像元宽度，um
        [IN] pixel_count: 像元总数
        [IN] bin_x: 水平方向binning倍数, 默认1即可.
        [IN] from1: 接谱起始波长范围
        [IN] to1: 接谱结束波长范围
        [IN] refwave: 参考波长, 默认500 nm
        [IN] edge: 边缘像素, 默认50
        [IN] op: 谱线数据覆盖率,  范围0.1 - 0.5
        [OUT] center_waves: 中心波长缓冲区，使用前初始化，大小为to - from即可
        [OUT] waves_count: 中心波长个数"""
        self.spectrometer1.spec_init_spectral_splice.argtypes = [
            ctypes.c_int, ctypes.c_float, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_int, ctypes.POINTER(ctypes.c_float), ctypes.POINTER(ctypes.c_float)]
        self.spectrometer1.spec_init_spectral_splice.restype = ctypes.c_bool

        serial_no_3 = ctypes.c_int(id1)
        pixel_width_1 = ctypes.c_float(pixel_width)
        pixel_count_1 = ctypes.c_int(pixel_count)
        binx_1 = ctypes.c_int(bin_x)
        from_1 = ctypes.c_float(from1)
        to_1 = ctypes.c_float(to1)
        refwave_1 = ctypes.c_float(refwave)
        op_1 = ctypes.c_float(op)
        nn = int(to1-from1+1)
        center_waves1 = (ctypes.c_float*nn)()
        waves_count1 = ctypes.c_int(88)
        is_true = self.spectrometer1.spec_init_spectral_splice(
            serial_no_3, pixel_width_1, pixel_count_1, binx_1, from_1, to_1, refwave_1, op_1, ctypes.byref(center_waves1), ctypes.byref(waves_count1))
        return is_true

    def spectral_splice(self, id1: int, x1, y1, size1, x2, y2, size2) -> bool:
        """开始接谱扫描，调用前请初始化参数。
        [IN] id1 : 单色仪的ID
        [IN] x1: 接谱前的波长数据
        [IN] y1: 接谱前的强度数据
        [IN] size1: 接谱前的波长/强度数据的长度
        [IN] x2: 待拼接的波长数据
        [IN] y2: 待拼接的强度数据
        [IN] size2: 待拼接的波长/强度数据的长度
        [OUT] x3: 拼接后的波长数据，使用前需初始化，大小为size1+size2即可
        [OUT] y3: 拼接后的强度数据，使用前需初始化，大小为size1+size2即可
        [OUT] size3: 拼接后的波长/强度数据的实际长度"""
        self.spectrometer1.spec_spectral_splice.argtypes = [
            ctypes.c_int, ctypes.POINTER(ctypes.c_float), ctypes.POINTER(ctypes.c_float), ctypes.c_int, ctypes.POINTER(ctypes.c_float), ctypes.POINTER(ctypes.c_float), ctypes.c_int, ctypes.POINTER(ctypes.c_float), ctypes.POINTER(ctypes.c_float), ctypes.c_int]
        self.spectrometer1.spec_spectral_splice.restype = ctypes.c_bool

        serial_no_3 = ctypes.c_int(id1)
        size_1 = ctypes.c_int(size1)
        size_2 = ctypes.c_int(size2)

        x3 = (ctypes.c_float*(size1+size2))()
        y3 = (ctypes.c_float*(size1+size2))()
        size_3 = ctypes.c_int(999)

        is_true = self.spectrometer1.spec_spectral_splice(
            serial_no_3, ctypes.pointer(x1), ctypes.pointer(y1), size_1, ctypes.pointer(x2), ctypes.pointer(y2), size_2,  ctypes.byref(x3), ctypes.byref(y3), ctypes.byref(size_3))
        return is_true, (x3[:size_3], y3[:size_3], size_3)

# -------用户自定义数据相关------------------------------------------------------------------
    def set_user_data(self, id1: int, offset, data, len1) -> bool:
        """向EEPROM中写入用户自定义数据，有效内存8190 kb。
        固件版本号3.4及以上可用#
        参数：
        id1 :  单色仪的ID。
        offset: 内存偏移位置。
        data: 自定义数据。
        len1: 自定义数据长度。
        返回值：
        true: 成功。
        false: 失败。"""
        self.spectrometer1.spec_set_user_data.argtypes = [
            ctypes.c_int, ctypes.c_short, ctypes.c_char_p, ctypes.c_short]
        self.spectrometer1.spec_set_user_data.restype = ctypes.c_bool

        serial_no_3 = ctypes.c_int(id1)
        offset_1 = ctypes.c_short(offset)
        data1 = data.encode()
        data_2 = ctypes.c_char_p(data1)
        len_1 = ctypes.c_short(len1)

        is_true = self.spectrometer1.spec_set_user_data(
            serial_no_3, offset_1, data_2, len_1)
        return is_true

    def get_user_data(self, id1: int, offset, len1):
        """读取EEPROM中用户写入的自定义数据，有效内存8190 kb
        件版本号3.4及以上可用#
        参数：
        id1 :  单色仪的ID。
        offset: 内存偏移位置。
        data: 读出数据缓存区。
        len: 读出数据缓存区大小。
        返回值：
        true: 成功。
        false: 失败。"""
        self.spectrometer1.spec_get_user_data.argtypes = [
            ctypes.c_int, ctypes.c_short, ctypes.c_char_p, ctypes.c_short]
        self.spectrometer1.spec_get_user_data.restype = ctypes.c_bool

        serial_no_3 = ctypes.c_int(id1)
        offset_1 = ctypes.c_short(offset)
        data1 = (ctypes.c_char*len1)()

        len_1 = ctypes.c_short(len1)

        is_true = self.spectrometer1.spec_get_user_data(
            serial_no_3, offset_1, data1, len_1)
        return is_true, data1.value

# -------自动光阑相关------------------------------------------------------------------
    def set_diaphragm(self, id1: int, which, where) -> bool:
        """设置光阑位置，仅HiperS-320i谱仪可用
        id1 :  单色仪的ID。
        which: 入口位置，0-侧入，1-直入。
        where: 光阑位置。"""
        self.spectrometer1.spec_set_diaphragm.argtypes = [
            ctypes.c_int, ctypes.c_int, ctypes.c_int]
        self.spectrometer1.spec_set_diaphragm.restype = ctypes.c_bool

        serial_no_3 = ctypes.c_int(id1)
        which_1 = ctypes.c_int(which)
        where_1 = ctypes.c_int(where)
        is_true = self.spectrometer1.spec_set_diaphragm(
            serial_no_3, which_1, where_1)
        return is_true

    def get_diaphragm(self, id1: int, which):
        """读取光阑位置，仅HiperS-320i谱仪可用
        id1 :  单色仪的ID。
        which: 入口位置，0-侧入，1-直入。
        where: 光阑位置。"""
        self.spectrometer1.spec_get_diaphragm.argtypes = [
            ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_int)]
        self.spectrometer1.spec_get_diaphragm.restype = ctypes.c_bool

        serial_no_3 = ctypes.c_int(id1)
        which_1 = ctypes.c_int(which)
        where_1 = ctypes.c_int(99)
        is_true = self.spectrometer1.spec_get_diaphragm(
            serial_no_3, which_1,  ctypes.byref(where_1))
        return is_true, where_1.value

    def set_diaphragm_steps(self, id1: int, which, where, steps) -> bool:
        """设置光阑指定位置的电机步数,仅HiperS-320i谱仪可用
        id1 :  单色仪的ID。
        which: 入口位置，0-侧入，1-直入。
        where: 光阑位置，范围：1~10。
        steps: 当前位置电机步数"""
        self.spectrometer1.spec_set_diaphragm_steps.argtypes = [
            ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_long]
        self.spectrometer1.spec_set_diaphragm_steps.restype = ctypes.c_bool

        serial_no_3 = ctypes.c_int(id1)
        which_1 = ctypes.c_int(which)
        where_1 = ctypes.c_int(where)
        steps_1 = ctypes.c_long(steps)
        is_true = self.spectrometer1.spec_set_diaphragm_steps(
            serial_no_3, which_1, where_1, steps_1)
        return is_true

    def get_diaphragm_steps(self, id1: int, which, where):
        """读取光阑指定位置的电机步数,仅HiperS-320i谱仪可用
        id1 :  单色仪的ID。
        which: 入口位置，0-侧入，1-直入。
        where: 光阑位置，范围：1~10。
        steps: 当前位置电机步数"""
        self.spectrometer1.spec_get_diaphragm_steps.argtypes = [
            ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_long)]
        self.spectrometer1.spec_get_diaphragm_steps.restype = ctypes.c_bool

        serial_no_3 = ctypes.c_int(id1)
        which_1 = ctypes.c_int(which)
        where_1 = ctypes.c_int(where)
        steps_1 = ctypes.c_long(19999)
        is_true = self.spectrometer1.spec_get_diaphragm_steps(
            serial_no_3, which_1, where_1, ctypes.byref(steps_1))
        return is_true, steps_1.value

# -------自动聚焦镜相关------------------------------------------------------------------
    # 聚焦镜位置对应关系表
    # 光栅号   实际位置    位置代号
    # 1   直入直出    1
    # 1   直入侧出    2
    # 1   侧入直出    3
    # 1   侧入侧出    4
    # 2   直入直出    5
    # 2   直入侧出    6
    # 2   侧入直出    7
    # 2   侧入侧出    8
    # 3   直入直出    9
    # 3   直入侧出    10
    # 3   侧入直出    11
    # 3   侧入侧出    12

    def set_focus_mirror(self, id1: int, where) -> bool:
        """设置聚焦镜位置,仅HiperS-320i谱仪可用
        id1 :  单色仪的ID
        where: 聚焦镜位置"""
        self.spectrometer1.spec_set_focus_mirror.argtypes = [
            ctypes.c_int, (ctypes.c_int)]
        self.spectrometer1.spec_set_focus_mirror.restype = ctypes.c_bool

        serial_no_3 = ctypes.c_int(id1)
        where_1 = ctypes.c_int(where)
        is_true = self.spectrometer1.spec_set_focus_mirror(
            serial_no_3, where_1)
        return is_true

    def get_focus_mirror(self, id1: int):
        """读取聚焦镜位置,仅HiperS-320i谱仪可用
        id1 :  单色仪的ID
        where: 聚焦镜位置"""
        self.spectrometer1.spec_get_focus_mirror.argtypes = [
            ctypes.c_int, ctypes.POINTER(ctypes.c_int)]
        self.spectrometer1.spec_get_focus_mirror.restype = ctypes.c_bool

        serial_no_3 = ctypes.c_int(id1)
        where1 = ctypes.c_int(123)

        is_true = self.spectrometer1.spec_get_focus_mirror(
            serial_no_3, ctypes.byref(where1))
        return is_true, where1.value

    def set_focus_mirror_steps(self, id1: int, grating_no) -> bool:
        """设置聚焦镜指定位置的电机步数，仅HiperS-320i谱仪可用
        id1 :  单色仪的ID。
        where: 聚焦镜位置，范围：1~12。
        steps: 当前位置电机步数"""
        self.spectrometer1.spec_set_focus_mirror_steps.argtypes = [
            ctypes.c_int, (ctypes.c_int)]
        self.spectrometer1.spec_set_focus_mirror_steps.restype = ctypes.c_bool

        serial_no_3 = ctypes.c_int(id1)
        grating_no = ctypes.c_int(grating_no)
        is_true = self.spectrometer1.spec_set_focus_mirror_steps(
            serial_no_3, (grating_no))
        # print('设置光栅序号为：{0}, 是否成功:{1}'.format( grating_no.value, is_true))
        return is_true

    def get_focus_mirror_steps(self, id1: int, where):
        """读取聚焦镜指定位置的电机步数，仅HiperS-320i谱仪可用
        id1 :  单色仪的ID。
        where: 聚焦镜位置，范围：1~12。
        steps: 当前位置电机步数"""
        self.spectrometer1.spec_get_focus_mirror_steps.argtypes = [
            ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_long)]
        self.spectrometer1.spec_get_focus_mirror_steps.restype = ctypes.c_bool

        serial_no_3 = ctypes.c_int(id1)
        position1 = ctypes.c_int(where)
        steps_1 = ctypes.c_long(999)
        is_true = self.spectrometer1.spec_get_focus_mirror_steps(
            serial_no_3, position1, ctypes.byref(steps_1))
        return is_true, steps_1.value
