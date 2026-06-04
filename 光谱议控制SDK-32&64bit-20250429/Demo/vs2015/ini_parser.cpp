#include "stdafx.h"
#include "ini_parser.h"


ini_parser::ini_parser()
{
}


ini_parser::~ini_parser()
{
}

void ini_parser::init(std::string path)
{
	_ini_path = path;
}

int ini_parser::get_int(std::string sec, std::string key)
{
	return GetPrivateProfileInt(to_cstring(sec), to_cstring(key), NULL, to_cstring(_ini_path));
}

void ini_parser::set_int(std::string sec, std::string key, int val)
{
	CString str;
	str.Format(_T("%d"), val);
	WritePrivateProfileString(to_cstring(sec), to_cstring(key), str, to_cstring(_ini_path));
}

double ini_parser::get_double(std::string sec, std::string key)
{
	TCHAR buf[200] = { 0 };
	int nSize = sizeof(buf) / sizeof(buf[0]);
	GetPrivateProfileString(to_cstring(sec), to_cstring(key), _T(""), buf, nSize, to_cstring(_ini_path));

	return _ttof(buf);
}

void ini_parser::set_double(std::string sec, std::string key, double val)
{
	CString str;
	str.Format(_T("%f"), val);
	WritePrivateProfileString(to_cstring(sec), to_cstring(key), str, to_cstring(_ini_path));
}

std::string ini_parser::get_string(std::string sec, std::string key)
{
	TCHAR buf[200] = { 0 };
	int nSize = sizeof(buf) / sizeof(buf[0]);
	GetPrivateProfileString(to_cstring(sec), to_cstring(key), _T(""), buf, nSize, to_cstring(_ini_path));

	return to_string(CString(buf));
}

void ini_parser::set_string(std::string sec, std::string key, std::string val)
{
	WritePrivateProfileString(to_cstring(sec), to_cstring(key), to_cstring(val), to_cstring(_ini_path));
}
