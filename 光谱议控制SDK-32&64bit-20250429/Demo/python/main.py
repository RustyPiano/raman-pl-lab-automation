# 注：如果python脚本无法正常连接谱仪，需要把python的IDE关闭重启，
# 再尝试重连，或者重启谱仪尝试
# 在python3.6.x版本测试无问题
# 主脚本，谱仪使用demo
import devices_spectrometer as devices



# 创建谱仪
spec1 = devices.Spectrometer()

# 由于python是通过动态库连接的谱仪硬件，有可能会发生连接问题，因此用异常处理
try:
    # 获取动态库的版本号
    dllver = spec1.get_dll_ver(12)
    print(f"动态库的版本号为:{dllver}")
    # 打开，并连接硬件设备
    num_dev = spec1.enum_dev_count()
    tt, num_sn = spec1.enum_dev_sn(num_dev-1,12)

    serial_no = spec1.open(num_sn)
    if serial_no < 0:
        print('谱仪连接失败')
    else:
        print('谱仪连接成功')

    # 设置谱仪为直出，侧入，设置成功会有声音
    spec1.set_exit_port(True)
    spec1.set_entrance_port(False) 

    # 设置自动狭缝宽度，如果有
    # spec1.set_slit_width(serial_no, 1, 15)

    # 设置光栅，转动到3号
    spec1.set_grating(1)

    # 设置中心波长转动到546nm
    spec1.move_to_wave(546)

    # 设置波长相对移动10nm
    spec1.move_wave(serial_no,10)

    # 获取当前光栅序号
    tt, cur_grating = spec1.get_grating(serial_no)
    if tt:
        print('当前光栅序号为：', cur_grating)


finally:
    # 完成后，关闭设备，
    spec1.close(serial_no)
    print('关闭设备')
