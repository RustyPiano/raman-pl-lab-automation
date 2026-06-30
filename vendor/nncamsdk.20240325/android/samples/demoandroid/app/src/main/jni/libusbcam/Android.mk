LOCAL_PATH:= $(call my-dir)
include $(CLEAR_VARS)  
LOCAL_MODULE := nncam
LOCAL_SRC_FILES := $(TARGET_ARCH_ABI)/libnncam.so
include $(PREBUILT_SHARED_LIBRARY)