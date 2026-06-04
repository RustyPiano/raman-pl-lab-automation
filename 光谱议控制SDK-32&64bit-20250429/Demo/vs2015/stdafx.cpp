
// stdafx.cpp : 只包括标准包含文件的源文件
// demo.pch 将作为预编译头
// stdafx.obj 将包含预编译类型信息

#include "stdafx.h"

int g_spec_id = -1;

std::string to_string(CString str)
{
#ifdef _UNICODE  
	//如果是unicode工程  
	USES_CONVERSION;
	std::string tmp(W2A(str));
	return std::move(tmp);
#else  
	//如果是多字节工程   
	std::string tmp(str.GetBuffer());
	str.ReleaseBuffer();
	return std::move(tmp);
#endif // _UNICODE
}

CString to_cstring(std::string str)
{
#ifdef _UNICODE  
	//如果是unicode工程  
	USES_CONVERSION;
	return std::move(A2W(str.c_str()));
#else  
	//如果是多字节工程   
	return std::move(CString(str.c_str()));
#endif // _UNICODE
}