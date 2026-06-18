## PL Mapping 测试流程: （适配Zolix光谱仪）

## 1. 找样。

a. 样品放置在样品台上, 打开MAPS软件, 点击Mode, 点击Image - LED切换成像光路。

b. 打开Camera，选择5x倍物镜。

I. 鼠标找样：选择合适的Focusing velocity通过鼠标滚轮聚焦样品表面。选择图像中左下角箭头按钮后，双击图像任意位置移动位移台寻找目标样品；

II. 手柄找样：1）左侧摇杆对应移动xy平面内的移动，摇杆+右上侧面按钮即快速移动找样。2）滚轮聚焦，上下滚动滚轮Z轴缓慢上下移动，向上或向下按下滚轮，Z轴较快上下移动。向上或向下按下滚轮+左上侧面按钮，Z轴超快速上下移动。

c. 物镜切换, 点击对应倍数即切换对应物镜, 或双击鼠标右键往大倍数切换物镜, Alt+双击右键往小倍数切换物镜。

![image](https://cdn-mineru.openxlab.org.cn/result/2026-06-18/6181bc27-eeaa-45db-9132-814afec8e38d/7fbfda88452b5295be365aa89f481edc3f8ee9a602dc51c84323e7363beb4819.jpg)


![image](https://cdn-mineru.openxlab.org.cn/result/2026-06-18/6181bc27-eeaa-45db-9132-814afec8e38d/53d0c473e8d9b2c0a972d5e6e728f4e8e2cc84591a4b3bc104f755a99e110499.jpg)


![image](https://cdn-mineru.openxlab.org.cn/result/2026-06-18/6181bc27-eeaa-45db-9132-814afec8e38d/0f57ac8314b8592cf9dc50b59bd402f6365beddeafb8a5838e937fda57cbdb5c.jpg)


![image](https://cdn-mineru.openxlab.org.cn/result/2026-06-18/6181bc27-eeaa-45db-9132-814afec8e38d/b4d380cb419b2a77dfd506ba0211ae30d1789c890e5b6ca3f0f27a2f8a3fe4f1.jpg)


## 2. 调节合适激光功率。

a. 打开Laser Power Adjust, 点击OK确认之后半波片会回到初始位置, Cancel则停在上一次实验结束半波片的位置。

b. 在框中输入激光数值功率, 确认后自动调整至目标功率。将标记激光位置的圆圈 (视场中心)移动至目标样品上准备测量PL/Raman。

![image](https://cdn-mineru.openxlab.org.cn/result/2026-06-18/6181bc27-eeaa-45db-9132-814afec8e38d/1af2855bacb9f37d199d44a4b31744e11f75b29519ac284d1312338d283caebd.jpg)


![image](https://cdn-mineru.openxlab.org.cn/result/2026-06-18/6181bc27-eeaa-45db-9132-814afec8e38d/405d00e8018389d2ef0055f396bf01c64ba6c7f7df47db5428541bb32a24a340.jpg)


![image](https://cdn-mineru.openxlab.org.cn/result/2026-06-18/6181bc27-eeaa-45db-9132-814afec8e38d/19c064d22640a6837873b3cb2ec90707202b1750358b3a647b29771cf0945a43.jpg)


## 3. Zolix光谱仪适配简介

a. 点击Sample Stage Mapping, 点亮Zolix弹出光谱仪界面, 等待初始化完成, Ready 之后可配置光谱仪常用参数。

b. 首先配置光谱仪入口与出口收集信号，INPUT FLIPPER为SIDE PORT，点击Set Port to，OUTPUT FLIPPER为DIRECT PORT，点击Set Port to，即配置完光谱仪侧入至直出口。

![image](https://cdn-mineru.openxlab.org.cn/result/2026-06-18/6181bc27-eeaa-45db-9132-814afec8e38d/c1aca1850e7ef5f22f9caeba10497536705faed389f47872f9b981dfde4303cb.jpg)


![image](https://cdn-mineru.openxlab.org.cn/result/2026-06-18/6181bc27-eeaa-45db-9132-814afec8e38d/591a251ee3c3481d5d0af03977802baa488ee6554208fad8566ba072c3c996fe.jpg)


![image](https://cdn-mineru.openxlab.org.cn/result/2026-06-18/6181bc27-eeaa-45db-9132-814afec8e38d/b908a7ec97bc7fe2b1a3fa5e1fede7b8f3921c14036ad2f355bfa04cc39dc024.jpg)


光栅选择, 输入1 2 or 3, 1: 1800  \mathrm{~g} 2: 600 \mathrm{~g} 3: 150 \mathrm{~g} , 点击Set Grating转到目标光栅

中心波长设置，输入数值，点击Set Wavelength to后调整至目标中心波长

![image](https://cdn-mineru.openxlab.org.cn/result/2026-06-18/6181bc27-eeaa-45db-9132-814afec8e38d/aec6e633324686bad9f519b3d2c392cd10d1b9a3a82228c1e8859f8537109c7a.jpg)


Slit选择INPUT SIDE，输入狭缝宽度，点击Set Slit to即可电动调整至目前狭缝宽度

## 4. 单点PL测量。

a. 点击Mode，选择PL/Raman切换光路准备初始单点数据测量。

b. 在Zolix光谱界面, 填选合适的积分时间, 点击Acq.收集光谱, Con. Acq.模式可连续拍谱实时观察信号变化。结合样品判断分析PL数据, 选择调整合适的各项参数: 中心波长, 光栅 (精度), 积分时间。

![image](https://cdn-mineru.openxlab.org.cn/result/2026-06-18/6181bc27-eeaa-45db-9132-814afec8e38d/b8e6b0a6306cb4f9993754f0850a7d3cc236f4e667339f8321ccf78b3014da8a.jpg)


![image](https://cdn-mineru.openxlab.org.cn/result/2026-06-18/6181bc27-eeaa-45db-9132-814afec8e38d/ebe90093e953fb3426bdfe5c1780bcf95ed5746fdcbf2cf14d5f2d3381566550.jpg)


![image](https://cdn-mineru.openxlab.org.cn/result/2026-06-18/6181bc27-eeaa-45db-9132-814afec8e38d/53abc80b058c59a5eafaf9a22325ed0574389d55fe3c2ee2f9b5081faf6107d7.jpg)


c. 减背景光谱信号测试：在Mode里点击 Laser off一键关闭激光，点击Acq.收集背景信号；在光谱界面点击Save BG保存背景、Sub BG减去背景，此时在Mode里点击 Laser on打开激光后，点击Acq.即为自动剪去背景噪声的光谱信号。点击Save 保存当前PL/Raman信号。

## 5. PL mapping测量。

a. 打开MAPS软件中Sample stage mapping, 点亮Use Camera Selection, 在Modes里切换Image-LED成像光路, 在相机成像的左下角中点击框选后框选目标mapping区域,并选择图像保存文件夹、填写样品Name, 点击Capture当前mapping图像保存;

b. 系统会自动识别框选的区域XY轴距离，根据测量需求设置Mapping步距参数，在Mode里点击PL/Raman切换至测试光路，点击运行开始Mapping测试。

![image](https://cdn-mineru.openxlab.org.cn/result/2026-06-18/6181bc27-eeaa-45db-9132-814afec8e38d/60824f4ceb4b65e89a6dfbfa763ae21b9eaae0a20726befeb76dc5bafe394313.jpg)


![image](https://cdn-mineru.openxlab.org.cn/result/2026-06-18/6181bc27-eeaa-45db-9132-814afec8e38d/d4bc64d781be88702f745a02b937ee45f31d7aeb283aae40c5c27fcabfbd8c53.jpg)


![image](https://cdn-mineru.openxlab.org.cn/result/2026-06-18/6181bc27-eeaa-45db-9132-814afec8e38d/1c5f4dc4531a7487ba66a25ae3abef6ac3f512da0ad32b2f7513578a3e9b1ed7.jpg)


![image](https://cdn-mineru.openxlab.org.cn/result/2026-06-18/6181bc27-eeaa-45db-9132-814afec8e38d/5b554e085ace4525374842ecbfb8889848c29980bc201bd7fb62d610d9be64d1.jpg)


## 6. 数据保存。

![image](https://cdn-mineru.openxlab.org.cn/result/2026-06-18/6181bc27-eeaa-45db-9132-814afec8e38d/6acc40e536f8676c85aad01782920fd5e6c7ed2c05bb624e7415d7d676c14fd7.jpg)



不同配色与平滑功能


a. 点击Mapping任意位置可实时在右侧显示点击位置的光谱信号，拖动右侧红蓝游标可以选择目标范围的光谱Mapping，左侧Mapping图像根据拖选范围实时更新。

b. 选择合适的光谱Mapping范围以及平滑图像，点击Save All Data可保存.tdms数据，可重新导入(Import Data)选择不同波长范围。

c. 点击Save Spec Data，保存单点光谱数据；点击Save Mapping Data，保存当前选择范围Mapping的txt文本数据；点击Save Image保存当前页面单点以及Mapping图像。

- ALL - X_29 - Y_29 - StepLength_0.520000 - ExpT_Ous.tdms 

- ALL - X_29 - Y_29 - StepLength_0.520000 - ExpT_Ous.tdms_index 

- Mapping - X_29 - Y_29 - StepLength_0.520um - Wavelength_691.07nm to 813.47nm 

- Mapping - X_29 - Y_29 - StepLength_0.520um - Wavelength_691.07nm to 813.47nm 

- Spectrum - - X_23 - Y_11 - ExpT_Ous 

- Spectrum - - X_23 - Y_11 - ExpT_Ous 