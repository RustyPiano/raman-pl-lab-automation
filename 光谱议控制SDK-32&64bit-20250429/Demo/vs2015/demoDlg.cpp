
// demoDlg.cpp : 实现文件
//
#include "stdafx.h"
#include "demo.h"
#include "demoDlg.h"
#include "afxdialogex.h"
#include <algorithm>

#ifdef _DEBUG
#define new DEBUG_NEW
#endif

#define WM_UPDATE_WAVE	(WM_USER + 1001)

// CdemoDlg 对话框

CdemoDlg::CdemoDlg(CWnd* pParent /*=NULL*/)
	: CDialogEx(IDD_DEMO_DIALOG, pParent)
	, m_nGrating(-1)
	, m_nEntrance(-1)
	, m_nExit(-1)
	, m_nFilter(-1)
	, m_bStop(false)
	, m_bHipers(false)
{
	m_hIcon = AfxGetApp()->LoadIcon(IDR_MAINFRAME);
}

void CdemoDlg::DoDataExchange(CDataExchange* pDX)
{
	CDialogEx::DoDataExchange(pDX);
	DDX_Radio(pDX, IDC_RADIO1, m_nGrating);
	DDX_Radio(pDX, IDC_RADIO4, m_nFilter);
	DDX_Radio(pDX, IDC_RADIO10, m_nEntrance);
	DDX_Radio(pDX, IDC_RADIO13, m_nExit);
	DDX_Control(pDX, IDC_BUTTON26, m_btFresh);
}

BEGIN_MESSAGE_MAP(CdemoDlg, CDialogEx)
	ON_WM_PAINT()
	ON_WM_QUERYDRAGICON()
	ON_BN_CLICKED(IDC_BUTTON3, &CdemoDlg::OnBnClickedButton3)
	ON_WM_CLOSE()
	ON_BN_CLICKED(IDC_BUTTON1, &CdemoDlg::OnBnClickedButton1)
	ON_BN_CLICKED(IDC_BUTTON2, &CdemoDlg::OnBnClickedButton2)
	ON_BN_CLICKED(IDC_BUTTON26, &CdemoDlg::OnBnClickedButton26)
	ON_BN_CLICKED(IDC_BUTTON13, &CdemoDlg::OnBnClickedButton13)
	ON_BN_CLICKED(IDC_RADIO1, &CdemoDlg::OnBnClickedRadio1)
	ON_BN_CLICKED(IDC_RADIO3, &CdemoDlg::OnBnClickedRadio3)
	ON_BN_CLICKED(IDC_RADIO2, &CdemoDlg::OnBnClickedRadio2)
	ON_BN_CLICKED(IDC_RADIO10, &CdemoDlg::OnBnClickedRadio10)
	ON_BN_CLICKED(IDC_RADIO12, &CdemoDlg::OnBnClickedRadio12)
	ON_BN_CLICKED(IDC_RADIO13, &CdemoDlg::OnBnClickedRadio13)
	ON_BN_CLICKED(IDC_RADIO15, &CdemoDlg::OnBnClickedRadio15)
	ON_BN_CLICKED(IDC_BUTTON4, &CdemoDlg::OnBnClickedButton4)
	ON_BN_CLICKED(IDC_BUTTON5, &CdemoDlg::OnBnClickedButton5)
	ON_BN_CLICKED(IDC_BUTTON40, &CdemoDlg::OnBnClickedButton40)
	ON_BN_CLICKED(IDC_CHECK1, &CdemoDlg::OnBnClickedCheck1)
	ON_BN_CLICKED(IDC_RADIO4, &CdemoDlg::OnBnClickedRadio4)
	ON_BN_CLICKED(IDC_RADIO5, &CdemoDlg::OnBnClickedRadio5)
	ON_BN_CLICKED(IDC_RADIO6, &CdemoDlg::OnBnClickedRadio6)
	ON_BN_CLICKED(IDC_RADIO7, &CdemoDlg::OnBnClickedRadio7)
	ON_BN_CLICKED(IDC_RADIO8, &CdemoDlg::OnBnClickedRadio8)
	ON_BN_CLICKED(IDC_RADIO9, &CdemoDlg::OnBnClickedRadio9)
	ON_BN_CLICKED(IDC_BUTTON6, &CdemoDlg::OnBnClickedButton6)
	ON_BN_CLICKED(IDC_BUTTON7, &CdemoDlg::OnBnClickedButton7)
	ON_BN_CLICKED(IDC_BUTTON8, &CdemoDlg::OnBnClickedButton8)
	ON_BN_CLICKED(IDC_BUTTON42, &CdemoDlg::OnBnClickedButton42)
	ON_BN_CLICKED(IDC_BUTTON44, &CdemoDlg::OnBnClickedButton44)
	ON_BN_CLICKED(IDC_BUTTON45, &CdemoDlg::OnBnClickedButton45)
	ON_BN_CLICKED(IDC_BUTTON49, &CdemoDlg::OnBnClickedButton49)
	ON_BN_CLICKED(IDC_BUTTON47, &CdemoDlg::OnBnClickedButton47)
	ON_BN_CLICKED(IDC_BUTTON51, &CdemoDlg::OnBnClickedButton51)
	ON_BN_CLICKED(IDC_CHECK5, &CdemoDlg::OnBnClickedCheck5)
	ON_BN_CLICKED(IDC_CHECK11, &CdemoDlg::OnBnClickedCheck11)
	ON_BN_CLICKED(IDC_BUTTON50, &CdemoDlg::OnBnClickedButton50)
	ON_BN_CLICKED(IDC_BUTTON46, &CdemoDlg::OnBnClickedButton46)
	ON_BN_CLICKED(IDC_BUTTON48, &CdemoDlg::OnBnClickedButton48)
	ON_BN_CLICKED(IDC_BUTTON52, &CdemoDlg::OnBnClickedButton52)
	ON_BN_CLICKED(IDC_BUTTON9, &CdemoDlg::OnBnClickedButton9)
	ON_BN_CLICKED(IDC_BUTTON53, &CdemoDlg::OnBnClickedButton53)
	ON_BN_CLICKED(IDC_BUTTON54, &CdemoDlg::OnBnClickedButton54)
	ON_CBN_SELCHANGE(IDC_COMBO2, &CdemoDlg::OnCbnSelchangeCombo2)
	ON_CBN_SELCHANGE(IDC_COMBO5, &CdemoDlg::OnCbnSelchangeCombo5)
	ON_BN_CLICKED(IDC_BUTTON23, &CdemoDlg::OnBnClickedButton23)
	ON_BN_CLICKED(IDC_BUTTON57, &CdemoDlg::OnBnClickedButton57)
	ON_BN_CLICKED(IDC_BUTTON56, &CdemoDlg::OnBnClickedButton56)
	ON_BN_CLICKED(IDC_BUTTON58, &CdemoDlg::OnBnClickedButton58)
	ON_CBN_SELCHANGE(IDC_COMBO3, &CdemoDlg::OnCbnSelchangeCombo3)
	ON_BN_CLICKED(IDC_BUTTON10, &CdemoDlg::OnBnClickedButton10)
	ON_BN_CLICKED(IDC_BUTTON55, &CdemoDlg::OnBnClickedButton55)
END_MESSAGE_MAP()


// CdemoDlg 消息处理程序

BOOL CdemoDlg::OnInitDialog()
{
	CDialogEx::OnInitDialog();

	// 设置此对话框的图标。  当应用程序主窗口不是对话框时，框架将自动
	//  执行此操作
	SetIcon(m_hIcon, TRUE);			// 设置大图标
	SetIcon(m_hIcon, FALSE);		// 设置小图标


	OnBnClickedButton26();

	return TRUE;  // 除非将焦点设置到控件，否则返回 TRUE
}

// 如果向对话框添加最小化按钮，则需要下面的代码
//  来绘制该图标。  对于使用文档/视图模型的 MFC 应用程序，
//  这将由框架自动完成。

void CdemoDlg::OnPaint()
{
	if (IsIconic())
	{
		CPaintDC dc(this); // 用于绘制的设备上下文

		SendMessage(WM_ICONERASEBKGND, reinterpret_cast<WPARAM>(dc.GetSafeHdc()), 0);

		// 使图标在工作区矩形中居中
		int cxIcon = GetSystemMetrics(SM_CXICON);
		int cyIcon = GetSystemMetrics(SM_CYICON);
		CRect rect;
		GetClientRect(&rect);
		int x = (rect.Width() - cxIcon + 1) / 2;
		int y = (rect.Height() - cyIcon + 1) / 2;

		// 绘制图标
		dc.DrawIcon(x, y, m_hIcon);
	}
	else
	{
		CDialogEx::OnPaint();
	}
}

//当用户拖动最小化窗口时系统调用此函数取得光标
//显示。
HCURSOR CdemoDlg::OnQueryDragIcon()
{
	return static_cast<HCURSOR>(m_hIcon);
}


#include "DlgAdvance.h"
void CdemoDlg::OnBnClickedButton3()
{
	// TODO: 在此添加控件通知处理程序代码
	CDlgAdvance dlg(this);
	dlg.DoModal();
}


void CdemoDlg::OnClose()
{
	// TODO: 在此添加消息处理程序代码和/或调用默认值

	if (spec_get_is_open(g_spec_id)) {
		spec_close(g_spec_id);
	}

	CDialogEx::OnClose();
}


void CdemoDlg::OnBnClickedButton1()
{
	// TODO: 在此添加控件通知处理程序代码
	CString sn;
	((CComboBox*)GetDlgItem(IDC_COMBO1))->GetWindowText(sn);

	auto str = to_string(sn);

	//spec_set_usb_mode(false);
	//g_spec_id = spec_open("COM96");
	spec_set_usb_mode(true);
	g_spec_id = spec_open(str.c_str());

	bool opened = spec_get_is_open(g_spec_id);
	if (!opened) {
		AfxMessageBox(_T("failed."));
	}
	else {
		((CButton*)GetDlgItem(IDC_BUTTON1))->EnableWindow(FALSE);
		((CButton*)GetDlgItem(IDC_BUTTON2))->EnableWindow(TRUE);
		((CButton*)GetDlgItem(IDC_BUTTON3))->EnableWindow(TRUE);
		((CButton*)GetDlgItem(IDC_BUTTON42))->EnableWindow(TRUE);

		//update_status();
	}
}


void CdemoDlg::OnBnClickedButton2()
{
	// TODO: 在此添加控件通知处理程序代码

	if (!spec_close(g_spec_id)) {
		AfxMessageBox(_T("断开连接失败."));
	}
	else {
		((CButton*)GetDlgItem(IDC_BUTTON1))->EnableWindow(TRUE);
		((CButton*)GetDlgItem(IDC_BUTTON2))->EnableWindow(FALSE);
		((CButton*)GetDlgItem(IDC_BUTTON3))->EnableWindow(FALSE);
		((CButton*)GetDlgItem(IDC_BUTTON42))->EnableWindow(FALSE);
	}
}


void CdemoDlg::update_status()
{
	int index = -1;
	long steps = -1;
	bool is_setup = false;
	bool front = false;
	float f_val = 0;
	CString str;

#pragma region Grating & Wavelength
	if (spec_get_grating(g_spec_id, &index)) {
		m_nGrating = index - 1;
	}

	if (spec_get_curr_wave(g_spec_id, &f_val)) {
		str.Format(_T("%g"), f_val);
		((CEdit*)GetDlgItem(IDC_EDIT6))->SetWindowText(str);
	}
#pragma endregion

#pragma region Mirror
	is_setup = false;
	if (spec_is_setup_mirror(g_spec_id, 0, &is_setup)) {
		if (is_setup) {
			//if (spec_get_exit_port(g_spec_id, &front)) {
			//	m_nExit = front ? 0 : 1;
			//}
		}
	}
	GetDlgItem(IDC_RADIO13)->EnableWindow(is_setup);
	GetDlgItem(IDC_RADIO15)->EnableWindow(is_setup);

	is_setup = false;
	if (spec_is_setup_mirror(g_spec_id, 1, &is_setup)) {
		if (is_setup) {
			//if (spec_get_entrance_port(g_spec_id, &front)) {
			//	m_nEntrance = front ? 0 : 1;
			//}
		}
	}
	GetDlgItem(IDC_RADIO10)->EnableWindow(is_setup);
	GetDlgItem(IDC_RADIO12)->EnableWindow(is_setup);
#pragma endregion

#pragma region Filter
	is_setup = false;
	if (spec_is_setup_filter(g_spec_id, 0, &is_setup)) {
		if (is_setup) {
			//bool automatic = false;
			//spec_get_filter_status(g_spec_id, 0, &automatic);
			//((CButton*)(GetDlgItem(IDC_CHECK1)))->SetCheck(automatic);

			//if (spec_get_filter(g_spec_id, 0, &index)) {
			//	m_nFilter = index - 1;
			//}
		}
	}
	GetDlgItem(IDC_BUTTON44)->EnableWindow(is_setup);
	GetDlgItem(IDC_CHECK1)->EnableWindow(is_setup);
	GetDlgItem(IDC_RADIO4)->EnableWindow(is_setup);
	GetDlgItem(IDC_RADIO6)->EnableWindow(is_setup);
	GetDlgItem(IDC_RADIO5)->EnableWindow(is_setup);
	GetDlgItem(IDC_RADIO7)->EnableWindow(is_setup);
	GetDlgItem(IDC_RADIO9)->EnableWindow(is_setup);
	GetDlgItem(IDC_RADIO8)->EnableWindow(is_setup);
#pragma endregion

#pragma region Slit
	//if (!spec_set_slit_factor(g_spec_id, 2.3)) {
	//	AfxMessageBox(_T("set slit factor failed."));
	//}

	is_setup = false;
	if (spec_is_setup_slit(g_spec_id, 3, &is_setup)) {
		if (is_setup) {
			//OnBnClickedButton45();
		}
	}
	GetDlgItem(IDC_EDIT65)->EnableWindow(is_setup);
	GetDlgItem(IDC_BUTTON45)->EnableWindow(is_setup);
	GetDlgItem(IDC_BUTTON46)->EnableWindow(is_setup);

	is_setup = false;
	if (spec_is_setup_slit(g_spec_id, 0, &is_setup)) {
		if (is_setup) {
			//OnBnClickedButton49();
		}
	}
	GetDlgItem(IDC_EDIT72)->EnableWindow(is_setup);
	GetDlgItem(IDC_BUTTON49)->EnableWindow(is_setup);
	GetDlgItem(IDC_BUTTON50)->EnableWindow(is_setup);

	is_setup = false;
	if (spec_is_setup_slit(g_spec_id, 2, &is_setup)) {
		if (is_setup) {
			//OnBnClickedButton47();
		}
	}
	GetDlgItem(IDC_EDIT68)->EnableWindow(is_setup);
	GetDlgItem(IDC_BUTTON47)->EnableWindow(is_setup);
	GetDlgItem(IDC_BUTTON48)->EnableWindow(is_setup);

	is_setup = false;
	if (spec_is_setup_slit(g_spec_id, 1, &is_setup)) {
		if (is_setup) {
			//OnBnClickedButton51();
		}
	}
	GetDlgItem(IDC_EDIT73)->EnableWindow(is_setup);
	GetDlgItem(IDC_BUTTON51)->EnableWindow(is_setup);
	GetDlgItem(IDC_BUTTON52)->EnableWindow(is_setup);
#pragma endregion

#pragma region Shutter
	is_setup = false;
	if (spec_is_setup_shutter(g_spec_id, 0, &is_setup)) {
		if (is_setup) {
			//bool is_open = false;
			//spec_get_shutter_status(g_spec_id, 0, &is_open);

			//((CButton*)GetDlgItem(IDC_CHECK5))->SetCheck(is_setup);
		}
	}
	GetDlgItem(IDC_CHECK5)->EnableWindow(is_setup);

	is_setup = false;
	if (spec_is_setup_shutter(g_spec_id, 1, &is_setup)) {
		if (is_setup) {
			//bool is_open = false;
			//spec_get_shutter_status(g_spec_id, 1, &is_open);

			//((CButton*)GetDlgItem(IDC_CHECK11))->SetCheck(is_setup);
		}
	}
	GetDlgItem(IDC_CHECK11)->EnableWindow(is_setup);
#pragma endregion

#pragma region Diaphragm
	spec_info info{};
	spec_get_dev_info(g_spec_id, &info);
	//转小写
	std::string cstr(info.model);
	std::transform(cstr.begin(), cstr.end(), cstr.begin(), ::tolower);

	m_bHipers = true;//(cstr.find("hipers320i") != std::string::npos);
	if (m_bHipers) {
		//Side
		spec_get_diaphragm(g_spec_id, 0, &index);
		((CComboBox*)GetDlgItem(IDC_COMBO2))->SetCurSel(index);
		if (index > 0) {
			spec_get_diaphragm_steps(g_spec_id, 0, index, &steps);
			str.Format(_T("%d"), steps);
			((CEdit*)GetDlgItem(IDC_EDIT69))->SetWindowText(str);
		}
		//Front
		spec_get_diaphragm(g_spec_id, 1, &index);
		((CComboBox*)GetDlgItem(IDC_COMBO5))->SetCurSel(index);
		if (index > 0) {
			spec_get_diaphragm_steps(g_spec_id, 0, index, &steps);
			str.Format(_T("%d"), steps);
			((CEdit*)GetDlgItem(IDC_EDIT71))->SetWindowText(str);
		}
	}
	//Side
	GetDlgItem(IDC_COMBO2)->EnableWindow(m_bHipers);
	GetDlgItem(IDC_BUTTON9)->EnableWindow(m_bHipers);
	GetDlgItem(IDC_EDIT69)->EnableWindow(m_bHipers);
	GetDlgItem(IDC_BUTTON53)->EnableWindow(m_bHipers);
	GetDlgItem(IDC_BUTTON54)->EnableWindow(m_bHipers);
	//Front
	GetDlgItem(IDC_COMBO5)->EnableWindow(m_bHipers);
	GetDlgItem(IDC_BUTTON23)->EnableWindow(m_bHipers);
	GetDlgItem(IDC_EDIT71)->EnableWindow(m_bHipers);
	GetDlgItem(IDC_BUTTON57)->EnableWindow(m_bHipers);
	GetDlgItem(IDC_BUTTON58)->EnableWindow(m_bHipers);
#pragma endregion

#pragma region Focus mirror
	if (m_bHipers) {
		spec_get_focus_mirror(g_spec_id, &index);
		((CComboBox*)GetDlgItem(IDC_COMBO3))->SetCurSel(index);
		if (index > 0) {
			spec_get_focus_mirror_steps(g_spec_id, index, &steps);
			str.Format(_T("%d"), steps);
			((CEdit*)GetDlgItem(IDC_EDIT70))->SetWindowText(str);
		}
	}
	GetDlgItem(IDC_COMBO3)->EnableWindow(m_bHipers);
	GetDlgItem(IDC_BUTTON10)->EnableWindow(m_bHipers);
	GetDlgItem(IDC_EDIT70)->EnableWindow(m_bHipers);
	GetDlgItem(IDC_BUTTON55)->EnableWindow(m_bHipers);
	GetDlgItem(IDC_BUTTON56)->EnableWindow(m_bHipers);
#pragma endregion

	UpdateData(FALSE);
}


void CdemoDlg::OnBnClickedButton26()
{
	// TODO: 在此添加控件通知处理程序代码
	((CComboBox*)GetDlgItem(IDC_COMBO1))->ResetContent();
	char ver[32] = { 0 };
	spec_get_dll_ver(ver, 32);

	auto count = spec_enum_dev_count();
	for (size_t i = 0; i < count; i++)
	{
		char sn[64] = { 0 };
		if (spec_enum_dev_sn(i, sn, 64) && strlen(sn) > 0) {
			((CComboBox*)GetDlgItem(IDC_COMBO1))->AddString(CString(sn));
			((CComboBox*)GetDlgItem(IDC_COMBO1))->SetCurSel(i);
		}
	}
}


void CdemoDlg::OnBnClickedButton13()
{
	// TODO: 在此添加控件通知处理程序代码

	float cur = .0f;
	if (spec_get_curr_wave(g_spec_id, &cur)) {
		CString str;
		str.Format(_T("%g"), cur);
		((CEdit*)GetDlgItem(IDC_EDIT6))->SetWindowText(str);
	}
	else {
		AfxMessageBox(_T("get cur wavelength failed."));
	}
}


void CdemoDlg::OnBnClickedRadio1()
{
	// TODO: 在此添加控件通知处理程序代码

	if (!spec_set_grating(g_spec_id, 1)) {
		AfxMessageBox(_T("get cur wavelength failed."));
		return;
	}

	OnBnClickedButton13();
}


void CdemoDlg::OnBnClickedRadio3()
{
	// TODO: 在此添加控件通知处理程序代码

	if (!spec_set_grating(g_spec_id, 3)) {
		AfxMessageBox(_T("get cur wavelength failed."));
		return;
	}

	OnBnClickedButton13();
}


void CdemoDlg::OnBnClickedRadio2()
{
	// TODO: 在此添加控件通知处理程序代码

	if (!spec_set_grating(g_spec_id, 2)) {
		AfxMessageBox(_T("get cur wavelength failed."));
		return;
	}

	OnBnClickedButton13();
}


void CdemoDlg::OnBnClickedRadio10()
{
	// TODO: 在此添加控件通知处理程序代码

	if (!spec_set_entrance_port(g_spec_id, true)) {
		AfxMessageBox(_T("set port failed."));
	}
}


void CdemoDlg::OnBnClickedRadio12()
{
	// TODO: 在此添加控件通知处理程序代码

	if (!spec_set_entrance_port(g_spec_id, false)) {
		AfxMessageBox(_T("set port failed."));
	}
}


void CdemoDlg::OnBnClickedRadio13()
{
	// TODO: 在此添加控件通知处理程序代码

	if (!spec_set_exit_port(g_spec_id, true)) {
		AfxMessageBox(_T("set port failed."));
	}
}


void CdemoDlg::OnBnClickedRadio15()
{
	// TODO: 在此添加控件通知处理程序代码

	if (!spec_set_exit_port(g_spec_id, false)) {
		AfxMessageBox(_T("set port failed."));
	}
}


void CdemoDlg::OnBnClickedButton4()
{
	// TODO: 在此添加控件通知处理程序代码
	CString str;
	((CEdit*)GetDlgItem(IDC_EDIT1))->GetWindowText(str);

	float wave = _ttof(str);
	if (!spec_move_wave(g_spec_id, wave)) {
		AfxMessageBox(_T("move wavelength failed."));
	}
	else {
		OnBnClickedButton13();
	}
}


void CdemoDlg::OnBnClickedButton5()
{
	// TODO: 在此添加控件通知处理程序代码
	CString str;
	((CEdit*)GetDlgItem(IDC_EDIT5))->GetWindowText(str);

	float wave = _ttof(str);
	if (!spec_move_to_wave(g_spec_id, wave)) {
		AfxMessageBox(_T("move wavelength failed."));
	}
	else {
		OnBnClickedButton13();
	}
}


void CdemoDlg::OnBnClickedButton40()
{
	// TODO: 在此添加控件通知处理程序代码
	char error[128] = { 0 };
	spec_get_error(g_spec_id, error, 128);

	CString str(error);
	AfxMessageBox(_T("Error Info: ") + str);
}


void CdemoDlg::OnBnClickedCheck1()
{
	// TODO: 在此添加控件通知处理程序代码
	auto atomatic = ((CButton*)GetDlgItem(IDC_CHECK1))->GetCheck();
	spec_set_filter_status(g_spec_id, 0, (atomatic == 1));
}


void CdemoDlg::OnBnClickedRadio4()
{
	// TODO: 在此添加控件通知处理程序代码

	if (!spec_set_filter(g_spec_id, 0, 1)) {
		AfxMessageBox(_T("Switch filtrt failed."));
	}
}


void CdemoDlg::OnBnClickedRadio5()
{
	// TODO: 在此添加控件通知处理程序代码

	if (!spec_set_filter(g_spec_id, 0, 2)) {
		AfxMessageBox(_T("Switch filtrt failed."));
	}
}


void CdemoDlg::OnBnClickedRadio6()
{
	// TODO: 在此添加控件通知处理程序代码
	if (!spec_set_filter(g_spec_id, 0, 3)) {
		AfxMessageBox(_T("Switch filtrt failed."));
	}
}


void CdemoDlg::OnBnClickedRadio7()
{
	// TODO: 在此添加控件通知处理程序代码

	if (!spec_set_filter(g_spec_id, 0, 4)) {
		AfxMessageBox(_T("Switch filtrt failed."));
	}
}


void CdemoDlg::OnBnClickedRadio8()
{
	// TODO: 在此添加控件通知处理程序代码
	if (!spec_set_filter(g_spec_id, 0, 5)) {
		AfxMessageBox(_T("Switch filtrt failed."));
	}
}


void CdemoDlg::OnBnClickedRadio9()
{
	// TODO: 在此添加控件通知处理程序代码
	if (!spec_set_filter(g_spec_id, 0, 6)) {
		AfxMessageBox(_T("Switch filtrt failed."));
	}
}


#include <thread>
void CdemoDlg::OnBnClickedButton6()
{
	// TODO: 在此添加控件通知处理程序代码

	CString strFrom, strTo, strStep;
	((CEdit*)GetDlgItem(IDC_EDIT2))->GetWindowText(strFrom);
	((CEdit*)GetDlgItem(IDC_EDIT3))->GetWindowText(strTo);
	((CEdit*)GetDlgItem(IDC_EDIT4))->GetWindowText(strStep);

	double dFrom = _ttof(strFrom);
	double dTo = _ttof(strTo);
	double dStep = _ttof(strStep);

	m_bStop = false;

	std::thread([=] {
		for (double wave = dFrom; wave <= dTo; wave += dStep)
		{
			if (m_bStop) break;

			if (!spec_move_to_wave(g_spec_id, wave)) {
				AfxMessageBox(_T("移动波长错误."));
				break;
			}

			CString str;
			str.Format(_T("%g"), wave);
			((CEdit*)GetDlgItem(IDC_EDIT6))->SetWindowText(str);
		}

		GetDlgItem(IDC_BUTTON6)->EnableWindow(TRUE);
		GetDlgItem(IDC_BUTTON7)->EnableWindow(FALSE);
	}).detach();

	GetDlgItem(IDC_BUTTON6)->EnableWindow(FALSE);
	GetDlgItem(IDC_BUTTON7)->EnableWindow(TRUE);
}

void CdemoDlg::OnBnClickedButton7()
{
	// TODO: 在此添加控件通知处理程序代码
	m_bStop = true;

	GetDlgItem(IDC_BUTTON6)->EnableWindow(TRUE);
	GetDlgItem(IDC_BUTTON7)->EnableWindow(FALSE);
}


void CdemoDlg::OnBnClickedButton8()
{
	// TODO: 在此添加控件通知处理程序代码
	((CEdit*)GetDlgItem(IDC_EDIT2))->SetWindowText(_T(""));
	((CEdit*)GetDlgItem(IDC_EDIT3))->SetWindowText(_T(""));
	((CEdit*)GetDlgItem(IDC_EDIT4))->SetWindowText(_T(""));
}

#include "DlgCorrect.h"
void CdemoDlg::OnBnClickedButton42()
{
	// TODO: 在此添加控件通知处理程序代码
	CDlgCorrect dlg(this);
	dlg.DoModal();
}


void CdemoDlg::OnBnClickedButton44()
{
	// TODO: 在此添加控件通知处理程序代码

	if (!spec_set_filter_home(g_spec_id, 0)) {
		AfxMessageBox(_T("Set filter home failed."));
	}
}


void CdemoDlg::OnBnClickedButton45()
{
	// TODO: 在此添加控件通知处理程序代码
	CString str;
	float bandpass = 0;

	if (spec_get_slit_bandpass(g_spec_id, 3, &bandpass)) {
		str.Format(_T("%g"), bandpass);
		((CEdit*)(GetDlgItem(IDC_EDIT65)))->SetWindowText(str);
	}
}


void CdemoDlg::OnBnClickedButton49()
{
	// TODO: 在此添加控件通知处理程序代码
	CString str;
	float bandpass = 0;

	if (spec_get_slit_bandpass(g_spec_id, 0, &bandpass)) {
		str.Format(_T("%g"), bandpass);
		((CEdit*)(GetDlgItem(IDC_EDIT72)))->SetWindowText(str);
	}
}


void CdemoDlg::OnBnClickedButton47()
{
	// TODO: 在此添加控件通知处理程序代码
	CString str;
	float bandpass = 0;
	if (spec_get_slit_bandpass(g_spec_id, 2, &bandpass)) {
		str.Format(_T("%g"), bandpass);
		((CEdit*)(GetDlgItem(IDC_EDIT68)))->SetWindowText(str);
	}
}


void CdemoDlg::OnBnClickedButton51()
{
	// TODO: 在此添加控件通知处理程序代码
	CString str;
	float bandpass = 0;

	if (spec_get_slit_bandpass(g_spec_id, 1, &bandpass)) {
		str.Format(_T("%g"), bandpass);
		((CEdit*)(GetDlgItem(IDC_EDIT73)))->SetWindowText(str);
	}
}


void CdemoDlg::OnBnClickedCheck5()
{
	// TODO: 在此添加控件通知处理程序代码
	int open = ((CButton*)GetDlgItem(IDC_CHECK5))->GetCheck();

	if (!spec_set_shutter_status(g_spec_id, 0, (open == 1))) {
		((CButton*)(GetDlgItem(IDC_CHECK5)))->SetCheck(!open);
		AfxMessageBox(_T("set shutter status failed."));
	}
}


void CdemoDlg::OnBnClickedCheck11()
{
	// TODO: 在此添加控件通知处理程序代码
	int open = ((CButton*)GetDlgItem(IDC_CHECK11))->GetCheck();

	if (!spec_set_shutter_status(g_spec_id, 1, (open == 1))) {
		((CButton*)(GetDlgItem(IDC_CHECK11)))->SetCheck(!open);
		AfxMessageBox(_T("set shutter status failed."));
	}
}


BOOL CdemoDlg::PreTranslateMessage(MSG* pMsg)
{
	// TODO: 在此添加专用代码和/或调用基类
	if (pMsg->message == WM_KEYDOWN) {
		if (pMsg->wParam == VK_RETURN || pMsg->wParam == VK_ESCAPE) {
			return TRUE;
		}
	}
	return CDialogEx::PreTranslateMessage(pMsg);
}


void CdemoDlg::OnBnClickedButton50()
{
	// TODO: 在此添加控件通知处理程序代码
	CString str;
	((CEdit*)(GetDlgItem(IDC_EDIT72)))->GetWindowText(str);

	float bandpass = _ttof(str);
	if (!spec_set_slit_bandpass(g_spec_id, 0, bandpass)) {
		AfxMessageBox(_T("set slit bandpass failed."));
	}
}


void CdemoDlg::OnBnClickedButton46()
{
	// TODO: 在此添加控件通知处理程序代码
	CString str;
	((CEdit*)(GetDlgItem(IDC_EDIT65)))->GetWindowText(str);

	float bandpass = _ttof(str);
	if (!spec_set_slit_bandpass(g_spec_id, 3, bandpass)) {
		AfxMessageBox(_T("set slit bandpass failed."));
	}
}


void CdemoDlg::OnBnClickedButton48()
{
	// TODO: 在此添加控件通知处理程序代码
	CString str;
	((CEdit*)(GetDlgItem(IDC_EDIT68)))->GetWindowText(str);

	float bandpass = _ttof(str);
	if (!spec_set_slit_bandpass(g_spec_id, 2, bandpass)) {
		AfxMessageBox(_T("set slit bandpass failed."));
	}
}


void CdemoDlg::OnBnClickedButton52()
{
	// TODO: 在此添加控件通知处理程序代码
	CString str;
	((CEdit*)(GetDlgItem(IDC_EDIT73)))->GetWindowText(str);

	float bandpass = _ttof(str);
	if (!spec_set_slit_bandpass(g_spec_id, 1, bandpass)) {
		AfxMessageBox(_T("set slit bandpass failed."));
	}
}


void CdemoDlg::OnBnClickedButton9()
{
	auto index = ((CComboBox*)GetDlgItem(IDC_COMBO2))->GetCurSel();
	spec_set_diaphragm(g_spec_id, 0, index);
}


void CdemoDlg::OnBnClickedButton53()
{
	auto index = ((CComboBox*)GetDlgItem(IDC_COMBO2))->GetCurSel();

	long steps = 0;
	spec_get_diaphragm_steps(g_spec_id, 0, index, &steps);

	CString wstr; wstr.Format(_T("%d"), steps);
	((CEdit*)GetDlgItem(IDC_EDIT69))->SetWindowText(wstr);
}


void CdemoDlg::OnBnClickedButton54()
{
	auto index = ((CComboBox*)GetDlgItem(IDC_COMBO2))->GetCurSel();

	CString wstr;
	((CEdit*)GetDlgItem(IDC_EDIT69))->GetWindowText(wstr);

	spec_set_diaphragm_steps(g_spec_id, 0, index, _ttol(wstr));
}


void CdemoDlg::OnCbnSelchangeCombo2()
{
	auto index = ((CComboBox*)GetDlgItem(IDC_COMBO2))->GetCurSel();
	if (index > 0) {
		//读取步数
		OnBnClickedButton53();
	}

	GetDlgItem(IDC_EDIT69)->EnableWindow(index > 0);
	GetDlgItem(IDC_BUTTON53)->EnableWindow(index > 0);
	GetDlgItem(IDC_BUTTON54)->EnableWindow(index > 0);
}


void CdemoDlg::OnCbnSelchangeCombo5()
{
	auto index = ((CComboBox*)GetDlgItem(IDC_COMBO5))->GetCurSel();
	if (index > 0) {
		//读取步数
		OnBnClickedButton57();
	}

	GetDlgItem(IDC_EDIT71)->EnableWindow(index > 0);
	GetDlgItem(IDC_BUTTON57)->EnableWindow(index > 0);
	GetDlgItem(IDC_BUTTON58)->EnableWindow(index > 0);
}


void CdemoDlg::OnBnClickedButton23()
{
	auto index = ((CComboBox*)GetDlgItem(IDC_COMBO5))->GetCurSel();
	spec_set_diaphragm(g_spec_id, 1, index);
}


void CdemoDlg::OnBnClickedButton57()
{
	auto index = ((CComboBox*)GetDlgItem(IDC_COMBO5))->GetCurSel();

	long steps = 0;
	spec_get_diaphragm_steps(g_spec_id, 1, index, &steps);

	CString wstr; wstr.Format(_T("%d"), steps);
	((CEdit*)GetDlgItem(IDC_EDIT71))->SetWindowText(wstr);
}


void CdemoDlg::OnBnClickedButton56()
{
	auto index = ((CComboBox*)GetDlgItem(IDC_COMBO3))->GetCurSel();

	CString wstr;
	((CEdit*)GetDlgItem(IDC_EDIT70))->GetWindowText(wstr);

	spec_set_focus_mirror_steps(g_spec_id, index, _ttol(wstr));
}


void CdemoDlg::OnBnClickedButton58()
{
	auto index = ((CComboBox*)GetDlgItem(IDC_COMBO5))->GetCurSel();

	CString wstr;
	((CEdit*)GetDlgItem(IDC_EDIT71))->GetWindowText(wstr);

	spec_set_diaphragm_steps(g_spec_id, 1, index, _ttol(wstr));
}


void CdemoDlg::OnCbnSelchangeCombo3()
{
	auto index = ((CComboBox*)GetDlgItem(IDC_COMBO3))->GetCurSel();
	if (index > 0) {
		//读取步数
		OnBnClickedButton55();
	}

	GetDlgItem(IDC_EDIT70)->EnableWindow(index > 0);
	GetDlgItem(IDC_BUTTON55)->EnableWindow(index > 0);
	GetDlgItem(IDC_BUTTON56)->EnableWindow(index > 0);
}


void CdemoDlg::OnBnClickedButton10()
{
	auto index = ((CComboBox*)GetDlgItem(IDC_COMBO3))->GetCurSel();
	spec_set_focus_mirror(g_spec_id, index);
}


void CdemoDlg::OnBnClickedButton55()
{
	auto index = ((CComboBox*)GetDlgItem(IDC_COMBO3))->GetCurSel();

	long steps = 0;
	spec_get_focus_mirror_steps(g_spec_id, index, &steps);

	CString wstr; wstr.Format(_T("%d"), steps);
	((CEdit*)GetDlgItem(IDC_EDIT70))->SetWindowText(wstr);
}
