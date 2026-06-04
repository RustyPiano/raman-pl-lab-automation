// DlgAdvance.cpp : 实现文件
//

#include "stdafx.h"
#include "demo.h"
#include "DlgAdvance.h"
#include "afxdialogex.h"

#include "demoDlg.h"

#include <algorithm>

// CDlgAdvance 对话框

IMPLEMENT_DYNAMIC(CDlgAdvance, CDialogEx)

CDlgAdvance::CDlgAdvance(CWnd* pParent /*=NULL*/)
	: CDialogEx(IDD_DIALOG_ADVANCE, pParent)
{
	m_bHipers = false;
}

CDlgAdvance::~CDlgAdvance()
{
}

void CDlgAdvance::DoDataExchange(CDataExchange* pDX)
{
	CDialogEx::DoDataExchange(pDX);
}


BEGIN_MESSAGE_MAP(CDlgAdvance, CDialogEx)
	ON_WM_SHOWWINDOW()
	ON_BN_CLICKED(IDC_BUTTON1, &CDlgAdvance::OnBnClickedButton1)
	ON_BN_CLICKED(IDC_BUTTON2, &CDlgAdvance::OnBnClickedButton2)
	ON_BN_CLICKED(IDC_BUTTON26, &CDlgAdvance::OnBnClickedButton26)
	ON_BN_CLICKED(IDC_BUTTON27, &CDlgAdvance::OnBnClickedButton27)
	ON_BN_CLICKED(IDC_BUTTON14, &CDlgAdvance::OnBnClickedButton14)
	ON_BN_CLICKED(IDC_BUTTON20, &CDlgAdvance::OnBnClickedButton20)
	ON_BN_CLICKED(IDC_BUTTON16, &CDlgAdvance::OnBnClickedButton16)
	ON_BN_CLICKED(IDC_BUTTON22, &CDlgAdvance::OnBnClickedButton22)
	ON_BN_CLICKED(IDC_BUTTON17, &CDlgAdvance::OnBnClickedButton17)
	ON_BN_CLICKED(IDC_BUTTON23, &CDlgAdvance::OnBnClickedButton23)
	ON_BN_CLICKED(IDC_BUTTON18, &CDlgAdvance::OnBnClickedButton18)
	ON_BN_CLICKED(IDC_BUTTON24, &CDlgAdvance::OnBnClickedButton24)
	ON_BN_CLICKED(IDC_BUTTON19, &CDlgAdvance::OnBnClickedButton19)
	ON_BN_CLICKED(IDC_BUTTON28, &CDlgAdvance::OnBnClickedButton28)
	ON_BN_CLICKED(IDC_BUTTON34, &CDlgAdvance::OnBnClickedButton34)
	ON_BN_CLICKED(IDC_BUTTON29, &CDlgAdvance::OnBnClickedButton29)
	ON_BN_CLICKED(IDC_BUTTON35, &CDlgAdvance::OnBnClickedButton35)
	ON_BN_CLICKED(IDC_BUTTON30, &CDlgAdvance::OnBnClickedButton30)
	ON_BN_CLICKED(IDC_BUTTON36, &CDlgAdvance::OnBnClickedButton36)
	ON_BN_CLICKED(IDC_BUTTON31, &CDlgAdvance::OnBnClickedButton31)
	ON_BN_CLICKED(IDC_BUTTON37, &CDlgAdvance::OnBnClickedButton37)
	ON_BN_CLICKED(IDC_BUTTON32, &CDlgAdvance::OnBnClickedButton32)
	ON_BN_CLICKED(IDC_BUTTON38, &CDlgAdvance::OnBnClickedButton38)
	ON_BN_CLICKED(IDC_BUTTON33, &CDlgAdvance::OnBnClickedButton33)
	ON_BN_CLICKED(IDC_BUTTON39, &CDlgAdvance::OnBnClickedButton39)
	ON_BN_CLICKED(IDC_CHECK2, &CDlgAdvance::OnBnClickedCheck2)
	ON_BN_CLICKED(IDC_CHECK4, &CDlgAdvance::OnBnClickedCheck4)
	ON_BN_CLICKED(IDC_CHECK3, &CDlgAdvance::OnBnClickedCheck3)
	ON_BN_CLICKED(IDC_CHECK7, &CDlgAdvance::OnBnClickedCheck7)
	ON_BN_CLICKED(IDC_CHECK6, &CDlgAdvance::OnBnClickedCheck6)
	ON_BN_CLICKED(IDC_CHECK8, &CDlgAdvance::OnBnClickedCheck8)
	ON_BN_CLICKED(IDC_CHECK5, &CDlgAdvance::OnBnClickedCheck5)
	ON_BN_CLICKED(IDC_CHECK10, &CDlgAdvance::OnBnClickedCheck10)
	ON_BN_CLICKED(IDC_CHECK9, &CDlgAdvance::OnBnClickedCheck9)
	ON_CBN_SELCHANGE(IDC_COMBO1, &CDlgAdvance::OnCbnSelchangeCombo1)
	ON_CBN_SELCHANGE(IDC_COMBO4, &CDlgAdvance::OnCbnSelchangeCombo4)
END_MESSAGE_MAP()


// CDlgAdvance 消息处理程序


void CDlgAdvance::OnShowWindow(BOOL bShow, UINT nStatus)
{
	CDialogEx::OnShowWindow(bShow, nStatus);

	// TODO: 在此处添加消息处理程序代码
	if (bShow) {
		//基本信息
		OnBnClickedButton1();
		//外设
		update_status();
		update_grating_info();
		update_filter_info();
		//IO
		OnBnClickedButton26();
	}
}

void CDlgAdvance::OnBnClickedButton1()
{
	// TODO: 在此添加控件通知处理程序代码
	spec_info info;
	if (spec_get_dev_info(g_spec_id, &info)) {
		GetDlgItem(IDC_EDIT1)->SetWindowText(CString(info.manufacturer));
		GetDlgItem(IDC_EDIT10)->SetWindowText(CString(info.model));
		GetDlgItem(IDC_EDIT11)->SetWindowText(CString(info.sn));
		GetDlgItem(IDC_EDIT12)->SetWindowText(CString(info.date));
		GetDlgItem(IDC_EDIT13)->SetWindowText(CString(info.firmware_ver));
	}
}


void CDlgAdvance::OnBnClickedButton2()
{
	// TODO: 在此添加控件通知处理程序代码

	CString str1, str2, str3, str4, str5;
	GetDlgItem(IDC_EDIT1)->GetWindowText(str1);
	GetDlgItem(IDC_EDIT10)->GetWindowText(str2);
	GetDlgItem(IDC_EDIT11)->GetWindowText(str3);
	GetDlgItem(IDC_EDIT12)->GetWindowText(str4);
	GetDlgItem(IDC_EDIT13)->GetWindowText(str5);

	spec_info info;
	memset(&info, 0, sizeof(spec_info));

	USES_CONVERSION;
	memcpy(info.manufacturer,W2A(str1), min(str1.GetLength(), 8));
	memcpy(info.model, W2A(str2), min(str2.GetLength(), 24));
	memcpy(info.sn, W2A(str3), min(str3.GetLength(), 24));
	memcpy(info.date, W2A(str4), min(str4.GetLength(), 9));
	memcpy(info.firmware_ver, W2A(str5), min(str4.GetLength(), 9));

	if (!spec_set_dev_info(g_spec_id,info)) {
		AfxMessageBox(_T("failed."));
	}
}

void CDlgAdvance::update_status()
{
	bool is_setup = false;

	//filter
	if (spec_is_setup_filter(g_spec_id, 0, &is_setup)) {
		((CButton*)GetDlgItem(IDC_CHECK2))->SetCheck(is_setup);
	}
	//en port
	if (spec_is_setup_mirror(g_spec_id, 1, &is_setup)) {
		((CButton*)GetDlgItem(IDC_CHECK4))->SetCheck(is_setup);
	}
	//exit port
	if (spec_is_setup_mirror(g_spec_id, 0, &is_setup)) {
		((CButton*)GetDlgItem(IDC_CHECK3))->SetCheck(is_setup);
	}
	//slit
	if (spec_is_setup_slit(g_spec_id, 3, &is_setup)) {
		((CButton*)GetDlgItem(IDC_CHECK7))->SetCheck(is_setup);
	}
	if (spec_is_setup_slit(g_spec_id, 0, &is_setup)) {
		((CButton*)GetDlgItem(IDC_CHECK6))->SetCheck(is_setup);
	}
	if (spec_is_setup_slit(g_spec_id, 2, &is_setup)) {
		((CButton*)GetDlgItem(IDC_CHECK8))->SetCheck(is_setup);
	}
	if (spec_is_setup_slit(g_spec_id, 1, &is_setup)) {
		((CButton*)GetDlgItem(IDC_CHECK5))->SetCheck(is_setup);
	}
	//shutter
	if (spec_is_setup_shutter(g_spec_id, 1, &is_setup)) {
		((CButton*)GetDlgItem(IDC_CHECK10))->SetCheck(is_setup);
	}
	if (spec_is_setup_shutter(g_spec_id, 0, &is_setup)) {
		((CButton*)GetDlgItem(IDC_CHECK9))->SetCheck(is_setup);
	}
}

void CDlgAdvance::update_grating_info()
{
	CString wstr;
	int index = -1;

	if (spec_get_turret(g_spec_id, &index)) {
		((CComboBox*)GetDlgItem(IDC_COMBO1))->SetCurSel(index - 1);
	}

	if (spec_get_init_grating(g_spec_id, &index)) {
		((CComboBox*)GetDlgItem(IDC_COMBO4))->SetCurSel(index - 1);
	}

	OnBnClickedButton14();
	OnBnClickedButton16();
	OnBnClickedButton17();
	OnBnClickedButton18();
	OnBnClickedButton19();
}

void CDlgAdvance::update_filter_info()
{
	OnBnClickedButton28();
	OnBnClickedButton29();
	OnBnClickedButton30();
	OnBnClickedButton31();
	OnBnClickedButton32();
	OnBnClickedButton33();
}


void CDlgAdvance::OnBnClickedButton26()
{
	// TODO: 在此添加控件通知处理程序代码
	
	short val = -1;
	if (spec_get_io_output(g_spec_id,&val)) {
		CString str;
		str.Format(_T("%d"), val);
		((CEdit*)GetDlgItem(IDC_EDIT32))->SetWindowText(str);
	}
}


void CDlgAdvance::OnBnClickedButton27()
{
	// TODO: 在此添加控件通知处理程序代码
	
	CString str;
	((CEdit*)GetDlgItem(IDC_EDIT32))->GetWindowText(str);

	short val = _ttoi(str);
	if (!spec_set_io_output(g_spec_id,val)) {
		AfxMessageBox(_T("Set io output failed."));
	}
}


void CDlgAdvance::OnBnClickedButton14()
{
	// TODO: 在此添加控件通知处理程序代码
	
	CString str;
	float init_wave = .0f;

	if (spec_get_init_wave(g_spec_id,1, &init_wave))
	{		
		str.Format(_T("%.f"));
		((CEdit*)GetDlgItem(IDC_EDIT14))->SetWindowText(str);
	}

	if (spec_get_init_wave(g_spec_id,2, &init_wave))
	{
		str.Format(_T("%.f"));
		((CEdit*)GetDlgItem(IDC_EDIT15))->SetWindowText(str);
	}

	if (spec_get_init_wave(g_spec_id,3, &init_wave))
	{
		str.Format(_T("%.f"));
		((CEdit*)GetDlgItem(IDC_EDIT16))->SetWindowText(str);
	}
}


void CDlgAdvance::OnBnClickedButton20()
{
	// TODO: 在此添加控件通知处理程序代码
	
	CString str;
	float init_wave = .0f;

	((CEdit*)GetDlgItem(IDC_EDIT14))->GetWindowText(str);
	if (str.GetLength() > 0 && !spec_set_init_wave(g_spec_id, 1, _ttof(str)))
	{
		AfxMessageBox(_T("Grating #1: set init wave failed."));
	}

	((CEdit*)GetDlgItem(IDC_EDIT15))->GetWindowText(str);
	if (str.GetLength() > 0 && !spec_set_init_wave(g_spec_id, 2, _ttof(str)))
	{
		AfxMessageBox(_T("Grating #2: set init wave failed."));
	}

	((CEdit*)GetDlgItem(IDC_EDIT16))->GetWindowText(str);
	if (str.GetLength() > 0 && spec_set_init_wave(g_spec_id, 3, _ttof(str)))
	{
		AfxMessageBox(_T("Grating #3: set init wave failed."));
	}
}

void CDlgAdvance::OnBnClickedButton16()
{
	// TODO: 在此添加控件通知处理程序代码
	
	int groove = 0;
	long blaze = 0;
	CString str;

	if (spec_get_grating_info(g_spec_id, 1, &groove, &blaze)) {
		str.Format(_T("%d"), groove);
		((CEdit*)GetDlgItem(IDC_EDIT17))->SetWindowText(str);
		str.Format(_T("%d"), blaze);
		((CEdit*)GetDlgItem(IDC_EDIT20))->SetWindowText(str);
	}

	if (spec_get_grating_info(g_spec_id, 2, &groove, &blaze)) {
		str.Format(_T("%d"), groove);
		((CEdit*)GetDlgItem(IDC_EDIT18))->SetWindowText(str);
		str.Format(_T("%d"), blaze);
		((CEdit*)GetDlgItem(IDC_EDIT21))->SetWindowText(str);
	}

	if (spec_get_grating_info(g_spec_id, 3, &groove, &blaze)) {
		str.Format(_T("%d"), groove);
		((CEdit*)GetDlgItem(IDC_EDIT19))->SetWindowText(str);
		str.Format(_T("%d"), blaze);
		((CEdit*)GetDlgItem(IDC_EDIT22))->SetWindowText(str);
	}
}


void CDlgAdvance::OnBnClickedButton22()
{
	// TODO: 在此添加控件通知处理程序代码
	
	CString str1;
	CString str2;

	((CEdit*)GetDlgItem(IDC_EDIT17))->GetWindowText(str1);
	((CEdit*)GetDlgItem(IDC_EDIT20))->GetWindowText(str2);
	if ((str1.GetLength() > 0 && str2.GetLength() > 0) && !spec_set_grating_info(g_spec_id, 1, _ttoi(str1), _ttol(str2)))
	{
		AfxMessageBox(_T("Grating #1: set info failed."));
	}

	((CEdit*)GetDlgItem(IDC_EDIT18))->GetWindowText(str1);
	((CEdit*)GetDlgItem(IDC_EDIT21))->GetWindowText(str2);
	if ((str1.GetLength() > 0 && str2.GetLength() > 0) && !spec_set_grating_info(g_spec_id, 2, _ttoi(str1), _ttol(str2)))
	{
		AfxMessageBox(_T("Grating #2: set info failed."));
	}

	((CEdit*)GetDlgItem(IDC_EDIT19))->GetWindowText(str1);
	((CEdit*)GetDlgItem(IDC_EDIT22))->GetWindowText(str2);
	if ((str1.GetLength() > 0 && str2.GetLength() > 0) && !spec_set_grating_info(g_spec_id, 3, _ttoi(str1), _ttol(str2)))
	{
		AfxMessageBox(_T("Grating #3: set info failed."));
	}
}


void CDlgAdvance::OnBnClickedButton17()
{
	// TODO: 在此添加控件通知处理程序代码
	
	CString str;
	long zero_pos = 0;

	short count = 0;
	spec_get_grating_count(g_spec_id, &count);

	if (spec_get_zero_pos(g_spec_id, 1, 0, &zero_pos)) {
		str.Format(_T("%ld"), zero_pos);
		((CEdit*)GetDlgItem(IDC_EDIT23))->SetWindowText(str);
	}

	if (count >= 2) {
		if (spec_get_zero_pos(g_spec_id, 2, 0, &zero_pos)) {
			str.Format(_T("%ld"), zero_pos);
			((CEdit*)GetDlgItem(IDC_EDIT24))->SetWindowText(str);
		}
	}
	
	if (count == 3) {
		if (spec_get_zero_pos(g_spec_id, 3, 0, &zero_pos)) {
			str.Format(_T("%ld"), zero_pos);
			((CEdit*)GetDlgItem(IDC_EDIT25))->SetWindowText(str);
		}
	}
}


void CDlgAdvance::OnBnClickedButton23()
{
	// TODO: 在此添加控件通知处理程序代码
	
	CString str;

	((CEdit*)GetDlgItem(IDC_EDIT23))->GetWindowText(str);
	if (str.GetLength() > 0 && !spec_set_zero_pos(g_spec_id, 1, 0, _ttol(str))) {
		AfxMessageBox(_T("Grating #1: set zero pos failed."));
	}

	((CEdit*)GetDlgItem(IDC_EDIT24))->GetWindowText(str);
	if (str.GetLength() > 0 && !spec_set_zero_pos(g_spec_id, 2, 0, _ttol(str))) {
		AfxMessageBox(_T("Grating #2: set zero pos failed."));
	}

	((CEdit*)GetDlgItem(IDC_EDIT25))->GetWindowText(str);
	if (str.GetLength() > 0 && !spec_set_zero_pos(g_spec_id, 3, 0, _ttol(str))) {
		AfxMessageBox(_T("Grating #3: set zero pos failed."));
	}
}


void CDlgAdvance::OnBnClickedButton18()
{
	// TODO: 在此添加控件通知处理程序代码
	
	CString str;
	float val = 0;

	short count = 0;
	spec_get_grating_count(g_spec_id, &count);

	if (spec_get_adjustment(g_spec_id, 1, &val)) {
		str.Format(_T("%g"), val);
		((CEdit*)GetDlgItem(IDC_EDIT26))->SetWindowText(str);
	}

	if (count >= 2 && spec_get_adjustment(g_spec_id, 2, &val)) {
		str.Format(_T("%g"), val);
		((CEdit*)GetDlgItem(IDC_EDIT27))->SetWindowText(str);
	}

	if (count == 3 && spec_get_adjustment(g_spec_id, 3, &val)) {
		str.Format(_T("%g"), val);
		((CEdit*)GetDlgItem(IDC_EDIT28))->SetWindowText(str);
	}
}


void CDlgAdvance::OnBnClickedButton24()
{
	// TODO: 在此添加控件通知处理程序代码
	
	CString str;

	((CEdit*)GetDlgItem(IDC_EDIT26))->GetWindowText(str);
	if (str.GetLength() > 0 && !spec_set_adjustment(g_spec_id, 1, _ttof(str))) {
		AfxMessageBox(_T("Grating #1: set adjustment failed."));
	}

	((CEdit*)GetDlgItem(IDC_EDIT27))->GetWindowText(str);
	if (str.GetLength() > 0 && !spec_set_adjustment(g_spec_id, 2, _ttof(str))) {
		AfxMessageBox(_T("Grating #2: set adjustment failed."));
	}

	((CEdit*)GetDlgItem(IDC_EDIT28))->GetWindowText(str);
	if (str.GetLength() > 0 && !spec_set_adjustment(g_spec_id, 3, _ttof(str))) {
		AfxMessageBox(_T("Grating #3: set adjustment failed."));
	}
}


void CDlgAdvance::OnBnClickedButton19()
{
	// TODO: 在此添加控件通知处理程序代码
	
	CString str;
	float val = 0;

	short count = 0;
	spec_get_grating_count(g_spec_id, &count);

	if (spec_get_max_wavelength(g_spec_id, 1, &val)) {
		str.Format(_T("%g"), val);
		((CEdit*)GetDlgItem(IDC_EDIT29))->SetWindowText(str);
	}

	if (count >= 2 && spec_get_max_wavelength(g_spec_id, 2, &val)) {
		str.Format(_T("%g"), val);
		((CEdit*)GetDlgItem(IDC_EDIT30))->SetWindowText(str);
	}

	if (count == 3 && spec_get_max_wavelength(g_spec_id, 3, &val)) {
		str.Format(_T("%g"), val);
		((CEdit*)GetDlgItem(IDC_EDIT31))->SetWindowText(str);
	}
}


void CDlgAdvance::OnBnClickedButton28()
{
	// TODO: 在此添加控件通知处理程序代码
	
	CString str;
	double limit = .0f;
	if (spec_get_filter_limit(g_spec_id, 1, 1, &limit)) {
		str.Format(_T("%g"), limit);
		((CEdit*)GetDlgItem(IDC_EDIT33))->SetWindowText(str);
	}

	if (spec_get_filter_limit(g_spec_id, 2, 1, &limit)) {
		str.Format(_T("%g"), limit);
		((CEdit*)GetDlgItem(IDC_EDIT34))->SetWindowText(str);
	}

	if (spec_get_filter_limit(g_spec_id, 3, 1, &limit)) {
		str.Format(_T("%g"), limit);
		((CEdit*)GetDlgItem(IDC_EDIT35))->SetWindowText(str);
	}
}


void CDlgAdvance::OnBnClickedButton34()
{
	// TODO: 在此添加控件通知处理程序代码

	CString str;

	((CEdit*)GetDlgItem(IDC_EDIT33))->GetWindowText(str);
	if (!spec_set_filter_limit(g_spec_id, 1, 1, _ttof(str)))
	{
		AfxMessageBox(_T("Grating #1: set filter limit failed."));
	}

	((CEdit*)GetDlgItem(IDC_EDIT34))->GetWindowText(str);
	if (!spec_set_filter_limit(g_spec_id, 2, 1, _ttol(str)))
	{
		AfxMessageBox(_T("Grating #2: set filter limit failed."));
	}

	((CEdit*)GetDlgItem(IDC_EDIT35))->GetWindowText(str);
	if (!spec_set_filter_limit(g_spec_id, 3, 1, _ttol(str)))
	{
		AfxMessageBox(_T("Grating #3: set filter limit failed."));
	}
}


void CDlgAdvance::OnBnClickedButton29()
{
	// TODO: 在此添加控件通知处理程序代码
	
	CString str;
	double limit = .0f;
	if (spec_get_filter_limit(g_spec_id, 1, 2, &limit)) {
		str.Format(_T("%g"), limit);
		((CEdit*)GetDlgItem(IDC_EDIT36))->SetWindowText(str);
	}

	if (spec_get_filter_limit(g_spec_id, 2, 2, &limit)) {
		str.Format(_T("%g"), limit);
		((CEdit*)GetDlgItem(IDC_EDIT37))->SetWindowText(str);
	}

	if (spec_get_filter_limit(g_spec_id, 3, 2, &limit)) {
		str.Format(_T("%g"), limit);
		((CEdit*)GetDlgItem(IDC_EDIT38))->SetWindowText(str);
	}
}


void CDlgAdvance::OnBnClickedButton35()
{
	// TODO: 在此添加控件通知处理程序代码
	
	CString str;

	((CEdit*)GetDlgItem(IDC_EDIT36))->GetWindowText(str);
	if (!spec_set_filter_limit(g_spec_id, 1, 2, _ttof(str)))
	{
		AfxMessageBox(_T("Grating #1: set filter limit failed."));
	}

	((CEdit*)GetDlgItem(IDC_EDIT37))->GetWindowText(str);
	if (!spec_set_filter_limit(g_spec_id, 2, 2, _ttol(str)))
	{
		AfxMessageBox(_T("Grating #2: set filter limit failed."));
	}

	((CEdit*)GetDlgItem(IDC_EDIT38))->GetWindowText(str);
	if (!spec_set_filter_limit(g_spec_id, 3, 2, _ttol(str)))
	{
		AfxMessageBox(_T("Grating #3: set filter limit failed."));
	}
}


void CDlgAdvance::OnBnClickedButton30()
{
	// TODO: 在此添加控件通知处理程序代码
	
	CString str;
	double limit = .0f;
	if (spec_get_filter_limit(g_spec_id, 1, 3, &limit)) {
		str.Format(_T("%g"), limit);
		((CEdit*)GetDlgItem(IDC_EDIT39))->SetWindowText(str);
	}

	if (spec_get_filter_limit(g_spec_id, 2, 3, &limit)) {
		str.Format(_T("%g"), limit);
		((CEdit*)GetDlgItem(IDC_EDIT40))->SetWindowText(str);
	}

	if (spec_get_filter_limit(g_spec_id, 3, 3, &limit)) {
		str.Format(_T("%g"), limit);
		((CEdit*)GetDlgItem(IDC_EDIT41))->SetWindowText(str);
	}
}


void CDlgAdvance::OnBnClickedButton36()
{
	// TODO: 在此添加控件通知处理程序代码
	
	CString str;

	((CEdit*)GetDlgItem(IDC_EDIT39))->GetWindowText(str);
	if (!spec_set_filter_limit(g_spec_id, 1, 3, _ttof(str)))
	{
		AfxMessageBox(_T("Grating #1: set filter limit failed."));
	}

	((CEdit*)GetDlgItem(IDC_EDIT40))->GetWindowText(str);
	if (!spec_set_filter_limit(g_spec_id, 2, 3, _ttol(str)))
	{
		AfxMessageBox(_T("Grating #2: set filter limit failed."));
	}

	((CEdit*)GetDlgItem(IDC_EDIT41))->GetWindowText(str);
	if (!spec_set_filter_limit(g_spec_id, 3, 3, _ttol(str)))
	{
		AfxMessageBox(_T("Grating #3: set filter limit failed."));
	}
}


void CDlgAdvance::OnBnClickedButton31()
{
	// TODO: 在此添加控件通知处理程序代码
	
	CString str;
	double limit = .0f;
	if (spec_get_filter_limit(g_spec_id, 1, 4, &limit)) {
		str.Format(_T("%g"), limit);
		((CEdit*)GetDlgItem(IDC_EDIT42))->SetWindowText(str);
	}

	if (spec_get_filter_limit(g_spec_id, 2, 4, &limit)) {
		str.Format(_T("%g"), limit);
		((CEdit*)GetDlgItem(IDC_EDIT43))->SetWindowText(str);
	}

	if (spec_get_filter_limit(g_spec_id, 3, 4, &limit)) {
		str.Format(_T("%g"), limit);
		((CEdit*)GetDlgItem(IDC_EDIT44))->SetWindowText(str);
	}
}


void CDlgAdvance::OnBnClickedButton37()
{
	// TODO: 在此添加控件通知处理程序代码
	
	CString str;

	((CEdit*)GetDlgItem(IDC_EDIT42))->GetWindowText(str);
	if (!spec_set_filter_limit(g_spec_id, 1, 4, _ttof(str)))
	{
		AfxMessageBox(_T("Grating #1: set filter limit failed."));
	}

	((CEdit*)GetDlgItem(IDC_EDIT43))->GetWindowText(str);
	if (!spec_set_filter_limit(g_spec_id, 2, 4, _ttol(str)))
	{
		AfxMessageBox(_T("Grating #2: set filter limit failed."));
	}

	((CEdit*)GetDlgItem(IDC_EDIT44))->GetWindowText(str);
	if (!spec_set_filter_limit(g_spec_id, 3, 4, _ttol(str)))
	{
		AfxMessageBox(_T("Grating #3: set filter limit failed."));
	}
}


void CDlgAdvance::OnBnClickedButton32()
{
	// TODO: 在此添加控件通知处理程序代码
	
	CString str;
	double limit = .0f;
	if (spec_get_filter_limit(g_spec_id, 1, 5, &limit)) {
		str.Format(_T("%g"), limit);
		((CEdit*)GetDlgItem(IDC_EDIT45))->SetWindowText(str);
	}

	if (spec_get_filter_limit(g_spec_id, 2, 5, &limit)) {
		str.Format(_T("%g"), limit);
		((CEdit*)GetDlgItem(IDC_EDIT46))->SetWindowText(str);
	}

	if (spec_get_filter_limit(g_spec_id, 3, 5, &limit)) {
		str.Format(_T("%g"), limit);
		((CEdit*)GetDlgItem(IDC_EDIT47))->SetWindowText(str);
	}
}


void CDlgAdvance::OnBnClickedButton38()
{
	// TODO: 在此添加控件通知处理程序代码
	
	CString str;

	((CEdit*)GetDlgItem(IDC_EDIT45))->GetWindowText(str);
	if (!spec_set_filter_limit(g_spec_id, 1, 5, _ttof(str)))
	{
		AfxMessageBox(_T("Grating #1: set filter limit failed."));
	}

	((CEdit*)GetDlgItem(IDC_EDIT46))->GetWindowText(str);
	if (!spec_set_filter_limit(g_spec_id, 2, 5, _ttol(str)))
	{
		AfxMessageBox(_T("Grating #2: set filter limit failed."));
	}

	((CEdit*)GetDlgItem(IDC_EDIT47))->GetWindowText(str);
	if (!spec_set_filter_limit(g_spec_id, 3, 5, _ttol(str)))
	{
		AfxMessageBox(_T("Grating #3: set filter limit failed."));
	}
}


void CDlgAdvance::OnBnClickedButton33()
{
	// TODO: 在此添加控件通知处理程序代码
	
	CString str;
	double limit = .0f;
	if (spec_get_filter_limit(g_spec_id, 1, 6, &limit)) {
		str.Format(_T("%g"), limit);
		((CEdit*)GetDlgItem(IDC_EDIT48))->SetWindowText(str);
	}

	if (spec_get_filter_limit(g_spec_id, 2, 6, &limit)) {
		str.Format(_T("%g"), limit);
		((CEdit*)GetDlgItem(IDC_EDIT49))->SetWindowText(str);
	}

	if (spec_get_filter_limit(g_spec_id, 3, 6, &limit)) {
		str.Format(_T("%g"), limit);
		((CEdit*)GetDlgItem(IDC_EDIT50))->SetWindowText(str);
	}
}


void CDlgAdvance::OnBnClickedButton39()
{
	// TODO: 在此添加控件通知处理程序代码
	
	CString str;

	((CEdit*)GetDlgItem(IDC_EDIT48))->GetWindowText(str);
	if (!spec_set_filter_limit(g_spec_id, 1, 6, _ttof(str)))
	{
		AfxMessageBox(_T("Grating #1: set filter limit failed."));
	}

	((CEdit*)GetDlgItem(IDC_EDIT49))->GetWindowText(str);
	if (!spec_set_filter_limit(g_spec_id, 2, 6, _ttol(str)))
	{
		AfxMessageBox(_T("Grating #2: set filter limit failed."));
	}

	((CEdit*)GetDlgItem(IDC_EDIT50))->GetWindowText(str);
	if (!spec_set_filter_limit(g_spec_id, 3, 6, _ttol(str)))
	{
		AfxMessageBox(_T("Grating #3: set filter limit failed."));
	}
}


void CDlgAdvance::OnBnClickedCheck2()
{
	// TODO: 在此添加控件通知处理程序代码
	
	int check = ((CButton*)GetDlgItem(IDC_CHECK2))->GetCheck();
	if (!spec_setup_filter(g_spec_id, 0, (check == 1))) {
		((CButton*)GetDlgItem(IDC_CHECK2))->SetCheck(!check);
		AfxMessageBox(_T("set filter status failed."));
	}
	else {
		CdemoDlg* pMain = (CdemoDlg*)GetParent();
		pMain->update_status();
	}
}


void CDlgAdvance::OnBnClickedCheck4()
{
	// TODO: 在此添加控件通知处理程序代码
	
	int check = ((CButton*)GetDlgItem(IDC_CHECK4))->GetCheck();
	if (!spec_setup_mirror(g_spec_id, 1, check == 1)) {
		((CButton*)GetDlgItem(IDC_CHECK4))->SetCheck(!check);
		AfxMessageBox(_T("set mirror status failed."));
	}
	else {
		CdemoDlg* pMain = (CdemoDlg*)GetParent();
		pMain->update_status();
	}
}


void CDlgAdvance::OnBnClickedCheck3()
{
	// TODO: 在此添加控件通知处理程序代码
	
	int check = ((CButton*)GetDlgItem(IDC_CHECK3))->GetCheck();
	if (!spec_setup_mirror(g_spec_id, 0, check == 1)) {
		((CButton*)GetDlgItem(IDC_CHECK3))->SetCheck(!check);
		AfxMessageBox(_T("set mirror status failed."));
	}
	else {
		CdemoDlg* pMain = (CdemoDlg*)GetParent();
		pMain->update_status();
	}
}


void CDlgAdvance::OnBnClickedCheck7()
{
	// TODO: 在此添加控件通知处理程序代码
	
	int check = ((CButton*)GetDlgItem(IDC_CHECK7))->GetCheck();
	if (!spec_setup_slit(g_spec_id, 3, check == 1)) {
		((CButton*)GetDlgItem(IDC_CHECK7))->SetCheck(!check);
		AfxMessageBox(_T("set slit status failed."));
	}
	else {
		CdemoDlg* pMain = (CdemoDlg*)GetParent();
		pMain->update_status();
	}
}


void CDlgAdvance::OnBnClickedCheck6()
{
	// TODO: 在此添加控件通知处理程序代码
	
	int check = ((CButton*)GetDlgItem(IDC_CHECK6))->GetCheck();
	if (!spec_setup_slit(g_spec_id, 0, check == 1)) {
		((CButton*)GetDlgItem(IDC_CHECK6))->SetCheck(!check);
		AfxMessageBox(_T("set slit status failed."));
	}
	else {
		CdemoDlg* pMain = (CdemoDlg*)GetParent();
		pMain->update_status();
	}
}


void CDlgAdvance::OnBnClickedCheck8()
{
	// TODO: 在此添加控件通知处理程序代码
	
	int check = ((CButton*)GetDlgItem(IDC_CHECK8))->GetCheck();
	if (!spec_setup_slit(g_spec_id, 2, check == 1)) {
		((CButton*)GetDlgItem(IDC_CHECK8))->SetCheck(!check);
		AfxMessageBox(_T("set slit status failed."));
	}
	else {
		CdemoDlg* pMain = (CdemoDlg*)GetParent();
		pMain->update_status();
	}
}


void CDlgAdvance::OnBnClickedCheck5()
{
	// TODO: 在此添加控件通知处理程序代码
	
	int check = ((CButton*)GetDlgItem(IDC_CHECK5))->GetCheck();
	if (!spec_setup_slit(g_spec_id, 1, check == 1)) {
		((CButton*)GetDlgItem(IDC_CHECK5))->SetCheck(!check);
		AfxMessageBox(_T("set slit status failed."));
	}
	else {
		CdemoDlg* pMain = (CdemoDlg*)GetParent();
		pMain->update_status();
	}
}


void CDlgAdvance::OnBnClickedCheck10()
{
	// TODO: 在此添加控件通知处理程序代码
	
	int check = ((CButton*)GetDlgItem(IDC_CHECK10))->GetCheck();
	if (!spec_setup_shutter(g_spec_id, 1, check == 1)) {
		((CButton*)GetDlgItem(IDC_CHECK10))->SetCheck(!check);
		AfxMessageBox(_T("set shutter status failed."));
	}
	else {
		CdemoDlg* pMain = (CdemoDlg*)GetParent();
		pMain->update_status();
	}
}


void CDlgAdvance::OnBnClickedCheck9()
{
	// TODO: 在此添加控件通知处理程序代码
	
	int check = ((CButton*)GetDlgItem(IDC_CHECK9))->GetCheck();
	if (!spec_setup_shutter(g_spec_id, 0, check == 1)) {
		((CButton*)GetDlgItem(IDC_CHECK9))->SetCheck(!check);
		AfxMessageBox(_T("set shutter status failed."));
	}
	else {
		CdemoDlg* pMain = (CdemoDlg*)GetParent();
		pMain->update_status();
	}
}


void CDlgAdvance::OnCbnSelchangeCombo1()
{
	// TODO: 在此添加控件通知处理程序代码
	
	int sel = ((CComboBox*)GetDlgItem(IDC_COMBO1))->GetCurSel();
	if (!spec_set_turret(g_spec_id, sel + 1)) {
		AfxMessageBox(_T("set turret failed."));
	}
}


void CDlgAdvance::OnCbnSelchangeCombo4()
{
	// TODO: 在此添加控件通知处理程序代码
	
	int sel = ((CComboBox*)GetDlgItem(IDC_COMBO4))->GetCurSel();
	if (!spec_set_init_grating(g_spec_id, sel + 1)) {
		AfxMessageBox(_T("set init grating failed."));
	}
}


BOOL CDlgAdvance::PreTranslateMessage(MSG* pMsg)
{
	// TODO: 在此添加专用代码和/或调用基类
	if (pMsg->message == WM_KEYDOWN) {
		if (pMsg->wParam == VK_RETURN || pMsg->wParam == VK_ESCAPE) {
			return TRUE;
		}
	}
	return CDialogEx::PreTranslateMessage(pMsg);
}