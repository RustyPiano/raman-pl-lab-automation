// DlgCorrect.cpp : 实现文件
//

#include "stdafx.h"
#include "demo.h"
#include "DlgCorrect.h"
#include "afxdialogex.h"

// CDlgCorrect 对话框
#include <chrono>
#include <memory>
#include <fstream>

#include "ini_parser.h"

IMPLEMENT_DYNAMIC(CDlgCorrect, CDialogEx)

CDlgCorrect::CDlgCorrect(CWnd* pParent /*=NULL*/)
	: CDialogEx(IDD_DIALOG_CORRECT, pParent)
	, m_nTurret(-1)
	, m_nGrating(-1)
	, m_fFoclen(0)
	, m_fAngdev(0)
	, m_fFoctlt(0)
	, m_fPoly1(0)
	, m_fPoly2(0)
	, m_fPoly3(0)
	, m_fPoly4(0)
	, m_fPoly5(0)
	, m_fAmp(0)
	, m_fPhase(0)
	, m_fFreq(0)
	, m_nStart(0)
	, m_sOffset(0)
	, m_fLines(0)
	, m_fBlaze(0)
	, m_sFront(0)
	, m_sSide(0)
{
	spec_set_ccd_mode(g_spec_id, true);
}

CDlgCorrect::~CDlgCorrect()
{
	spec_set_ccd_mode(g_spec_id, false);
}

void CDlgCorrect::DoDataExchange(CDataExchange* pDX)
{
	CDialogEx::DoDataExchange(pDX);
	DDX_Text(pDX, IDC_EDIT1, m_fFoclen);
	DDX_Text(pDX, IDC_EDIT10, m_fAngdev);
	DDX_Text(pDX, IDC_EDIT11, m_fFoctlt);
	DDX_Text(pDX, IDC_EDIT12, m_fPoly1);
	DDX_Text(pDX, IDC_EDIT13, m_fPoly2);
	DDX_Text(pDX, IDC_EDIT14, m_fPoly3);
	DDX_Text(pDX, IDC_EDIT15, m_fPoly4);
	DDX_Text(pDX, IDC_EDIT16, m_fPoly5);
	DDX_Text(pDX, IDC_EDIT17, m_fAmp);
	DDX_Text(pDX, IDC_EDIT18, m_fPhase);
	DDX_Text(pDX, IDC_EDIT19, m_fFreq);
	DDX_Text(pDX, IDC_EDIT20, m_nStart);
	DDX_Text(pDX, IDC_EDIT21, m_sOffset);
	DDX_Text(pDX, IDC_EDIT22, m_fLines);
	DDX_Text(pDX, IDC_EDIT23, m_fBlaze);
	DDX_Text(pDX, IDC_EDIT35, m_sFront);
	DDX_Text(pDX, IDC_EDIT36, m_sSide);
}


BEGIN_MESSAGE_MAP(CDlgCorrect, CDialogEx)
	ON_WM_SHOWWINDOW()
	ON_BN_CLICKED(IDC_BUTTON1, &CDlgCorrect::OnBnClickedButton1)
	ON_BN_CLICKED(IDC_BUTTON2, &CDlgCorrect::OnBnClickedButton2)
	ON_BN_CLICKED(IDC_BUTTON17, &CDlgCorrect::OnBnClickedButton17)
	ON_BN_CLICKED(IDC_BUTTON43, &CDlgCorrect::OnBnClickedButton43)
	ON_BN_CLICKED(IDC_BUTTON42, &CDlgCorrect::OnBnClickedButton42)
	ON_BN_CLICKED(IDC_BUTTON52, &CDlgCorrect::OnBnClickedButton52)
	ON_BN_CLICKED(IDC_BUTTON3, &CDlgCorrect::OnBnClickedButton3)
	ON_BN_CLICKED(IDC_BUTTON15, &CDlgCorrect::OnBnClickedButton15)
	ON_BN_CLICKED(IDC_BUTTON16, &CDlgCorrect::OnBnClickedButton16)
	ON_BN_CLICKED(IDC_BUTTON18, &CDlgCorrect::OnBnClickedButton18)
END_MESSAGE_MAP()


// CDlgCorrect 消息处理程序


BOOL CDlgCorrect::OnInitDialog()
{
	CDialogEx::OnInitDialog();

	// TODO:  在此添加额外的初始化
	if (spec_get_turret(g_spec_id, &m_nTurret)) {
		CString title;
		GetWindowText(title);

		title.Format(_T("%s - Turret %d"), title, m_nTurret);
		SetWindowText(title);
	}

	if (spec_get_grating(g_spec_id, &m_nGrating)) {
		CString title;
		GetWindowText(title);

		title.Format(_T("%s - Grating %d"), title, m_nGrating);
		SetWindowText(title);
	}

	auto ptr = (CListCtrl*)GetDlgItem(IDC_LIST1);
	ptr->InsertColumn(0, _T("pixel"), LVCFMT_LEFT, 100);
	ptr->InsertColumn(1, _T("wavelength"), LVCFMT_LEFT, 100);

	return TRUE;  // return TRUE unless you set the focus to a control
				  // 异常: OCX 属性页应返回 FALSE
}


void CDlgCorrect::OnShowWindow(BOOL bShow, UINT nStatus)
{
	CDialogEx::OnShowWindow(bShow, nStatus);

	// TODO: 在此处添加消息处理程序代码
	if (bShow) {
		OnBnClickedButton1();
		OnBnClickedButton17();
	}
}


void CDlgCorrect::OnBnClickedButton1()
{
	// TODO: 在此添加控件通知处理程序代码
	if (m_nTurret <= 0) {
		AfxMessageBox(_T("读取塔台序号失败."));
		return;
	}

	if (m_nGrating <= 0) {
		AfxMessageBox(_T("读取光栅序号失败."));
		return;
	}

	float f_val = 0;
	int n_val;
	short s_val;
	double d_val = 0;

	CString tmp;

	spec_info info;
	if (!spec_get_dev_info(g_spec_id, &info)) {
		AfxMessageBox(_T("读取版本信息失败."));
		return;
	}

	if (atof(info.firmware_ver + 1) >= 3.4) {
		if (spec_get_correct_params(g_spec_id, 1, m_nGrating, 0, &f_val)) {
			tmp.Format(_T("%g"), f_val);
			((CEdit*)GetDlgItem(IDC_EDIT1))->SetWindowText(tmp);
		}

		if (spec_get_correct_params(g_spec_id, 1, m_nGrating, 1, &f_val)) {
			tmp.Format(_T("%g"), f_val);
			((CEdit*)GetDlgItem(IDC_EDIT10))->SetWindowText(tmp);
		}

		if (spec_get_correct_params(g_spec_id, 1, m_nGrating, 2, &f_val)) {
			tmp.Format(_T("%g"), f_val);
			((CEdit*)GetDlgItem(IDC_EDIT11))->SetWindowText(tmp);
		}

		if (spec_get_correct_params(g_spec_id, 1, m_nGrating, 3, &d_val)) {
			tmp.Format(_T("%g"), d_val);
			((CEdit*)GetDlgItem(IDC_EDIT12))->SetWindowText(tmp);
		}

		if (spec_get_correct_params(g_spec_id, 1, m_nGrating, 4, &d_val)) {
			tmp.Format(_T("%g"), d_val);
			((CEdit*)GetDlgItem(IDC_EDIT13))->SetWindowText(tmp);
		}

		if (spec_get_correct_params(g_spec_id, 1, m_nGrating, 5, &d_val)) {
			tmp.Format(_T("%g"), d_val);
			((CEdit*)GetDlgItem(IDC_EDIT14))->SetWindowText(tmp);
		}

		if (spec_get_correct_params(g_spec_id, 1, m_nGrating, 6, &d_val)) {
			tmp.Format(_T("%g"), d_val);
			((CEdit*)GetDlgItem(IDC_EDIT15))->SetWindowText(tmp);
		}

		if (spec_get_correct_params(g_spec_id, 1, m_nGrating, 7, &d_val)) {
			tmp.Format(_T("%g"), d_val);
			((CEdit*)GetDlgItem(IDC_EDIT16))->SetWindowText(tmp);
		}

		if (spec_get_correct_params(g_spec_id, 1, m_nGrating, 8, &d_val)) {
			tmp.Format(_T("%g"), d_val);
			((CEdit*)GetDlgItem(IDC_EDIT17))->SetWindowText(tmp);
		}

		if (spec_get_correct_params(g_spec_id, 1, m_nGrating, 9, &d_val)) {
			tmp.Format(_T("%g"), d_val);
			((CEdit*)GetDlgItem(IDC_EDIT18))->SetWindowText(tmp);
		}

		if (spec_get_correct_params(g_spec_id, 1, m_nGrating, 10, &d_val)) {
			tmp.Format(_T("%g"), d_val);
			((CEdit*)GetDlgItem(IDC_EDIT19))->SetWindowText(tmp);
		}

		if (spec_get_correct_params(g_spec_id, 1, m_nGrating, 11, &n_val)) {
			tmp.Format(_T("%d"), n_val);
			((CEdit*)GetDlgItem(IDC_EDIT20))->SetWindowText(tmp);
		}

		if (spec_get_correct_params(g_spec_id, 1, m_nGrating, 12, &s_val)) {
			tmp.Format(_T("%d"), s_val);
			((CEdit*)GetDlgItem(IDC_EDIT21))->SetWindowText(tmp);
		}

		if (spec_get_correct_params(g_spec_id, 1, m_nGrating, 13, &d_val)) {
			tmp.Format(_T("%g"), d_val);
			((CEdit*)GetDlgItem(IDC_EDIT22))->SetWindowText(tmp);
		}

		if (spec_get_correct_params(g_spec_id, 1, m_nGrating, 14, &d_val)) {
			tmp.Format(_T("%g"), d_val);
			((CEdit*)GetDlgItem(IDC_EDIT23))->SetWindowText(tmp);
		}
	}
	else {
		unsigned char buff[4] = { 0 };
		spec_get_user_data(g_spec_id, 21, buff, 4);
		m_ver.assign(buff, buff + 4);

		GetWindowText(tmp);
		SetWindowText(tmp + _T(" - SVERNO:") + CString(buff));

		if (spec_get_correct_params(g_spec_id, 1, m_nGrating, 0, &f_val)) {
			tmp.Format(_T("%g"), f_val);
			((CEdit*)GetDlgItem(IDC_EDIT1))->SetWindowText(tmp);
		}

		if (spec_get_correct_params(g_spec_id, 1, m_nGrating, 1, &f_val)) {
			tmp.Format(_T("%g"), f_val);
			((CEdit*)GetDlgItem(IDC_EDIT10))->SetWindowText(tmp);
		}

		if (spec_get_correct_params(g_spec_id, 1, m_nGrating, 2, &f_val)) {
			tmp.Format(_T("%g"), f_val);
			((CEdit*)GetDlgItem(IDC_EDIT11))->SetWindowText(tmp);
		}

		if (spec_get_correct_params(g_spec_id, 1, m_nGrating, 3, &f_val)) {
			tmp.Format(_T("%g"), f_val);
			((CEdit*)GetDlgItem(IDC_EDIT12))->SetWindowText(tmp);
		}

		if (spec_get_correct_params(g_spec_id, 1, m_nGrating, 4, &f_val)) {
			tmp.Format(_T("%g"), f_val);
			((CEdit*)GetDlgItem(IDC_EDIT13))->SetWindowText(tmp);
		}

		if (spec_get_correct_params(g_spec_id, 1, m_nGrating, 5, &f_val)) {
			tmp.Format(_T("%g"), f_val);
			((CEdit*)GetDlgItem(IDC_EDIT14))->SetWindowText(tmp);
		}

		if (spec_get_correct_params(g_spec_id, 1, m_nGrating, 6, &f_val)) {
			tmp.Format(_T("%g"), f_val);
			((CEdit*)GetDlgItem(IDC_EDIT15))->SetWindowText(tmp);
		}

		if (spec_get_correct_params(g_spec_id, 1, m_nGrating, 7, &f_val)) {
			tmp.Format(_T("%g"), f_val);
			((CEdit*)GetDlgItem(IDC_EDIT16))->SetWindowText(tmp);
		}

		if (spec_get_correct_params(g_spec_id, 1, m_nGrating, 8, &f_val)) {
			tmp.Format(_T("%g"), f_val);
			((CEdit*)GetDlgItem(IDC_EDIT17))->SetWindowText(tmp);
		}

		if (spec_get_correct_params(g_spec_id, 1, m_nGrating, 9, &f_val)) {
			tmp.Format(_T("%g"), f_val);
			((CEdit*)GetDlgItem(IDC_EDIT18))->SetWindowText(tmp);
		}

		if (spec_get_correct_params(g_spec_id, 1, m_nGrating, 10, &f_val)) {
			tmp.Format(_T("%g"), f_val);
			((CEdit*)GetDlgItem(IDC_EDIT19))->SetWindowText(tmp);
		}

		if (spec_get_correct_params(g_spec_id, 1, m_nGrating, 11, &n_val)) {
			tmp.Format(_T("%d"), n_val);
			((CEdit*)GetDlgItem(IDC_EDIT20))->SetWindowText(tmp);
		}

		if (spec_get_correct_params(g_spec_id, 1, m_nGrating, 12, &n_val)) {
			tmp.Format(_T("%d"), n_val);
			((CEdit*)GetDlgItem(IDC_EDIT21))->SetWindowText(tmp);
		}

		if (spec_get_correct_params(g_spec_id, 1, m_nGrating, 13, &f_val)) {
			tmp.Format(_T("%g"), f_val);
			((CEdit*)GetDlgItem(IDC_EDIT22))->SetWindowText(tmp);
		}
	}
}


void CDlgCorrect::OnBnClickedButton2()
{
	// TODO: 在此添加控件通知处理程序代码
	
	float f_val = 0;
	int n_val;
	short s_val = 0;
	double d_val = 0;
	CString tmp;

	spec_info info;
	if (!spec_get_dev_info(g_spec_id, &info)) {
		AfxMessageBox(_T("读取版本信息失败."));
		return;
	}

	if (atof(info.firmware_ver + 1) >= 3.4) {
		((CEdit*)GetDlgItem(IDC_EDIT1))->GetWindowText(tmp);
		f_val = _ttof(tmp);
		if (!spec_set_correct_params(g_spec_id, 1, m_nGrating, 0, &f_val)) {
			AfxMessageBox(_T("焦距设置错误."));
		}

		((CEdit*)GetDlgItem(IDC_EDIT10))->GetWindowText(tmp);
		f_val = _ttof(tmp);
		if (!spec_set_correct_params(g_spec_id, 1, m_nGrating, 1, &f_val)) {
			AfxMessageBox(_T("内置角设置错误."));
		}

		((CEdit*)GetDlgItem(IDC_EDIT11))->GetWindowText(tmp);
		f_val = _ttof(tmp);
		if (!spec_set_correct_params(g_spec_id, 1, m_nGrating, 2, &f_val)) {
			AfxMessageBox(_T("焦面倾斜角设置错误."));
		}

		((CEdit*)GetDlgItem(IDC_EDIT12))->GetWindowText(tmp);
		d_val = _ttof(tmp);
		if (!spec_set_correct_params(g_spec_id, 1, m_nGrating, 3, &d_val)) {
			AfxMessageBox(_T("校正系数1设置错误."));
		}

		((CEdit*)GetDlgItem(IDC_EDIT13))->GetWindowText(tmp);
		d_val = _ttof(tmp);
		if (!spec_set_correct_params(g_spec_id, 1, m_nGrating, 4, &d_val)) {
			AfxMessageBox(_T("校正系数2设置错误."));
		}

		((CEdit*)GetDlgItem(IDC_EDIT14))->GetWindowText(tmp);
		d_val = _ttof(tmp);
		if (!spec_set_correct_params(g_spec_id, 1, m_nGrating, 5, &d_val)) {
			AfxMessageBox(_T("校正系数3设置错误."));
		}

		((CEdit*)GetDlgItem(IDC_EDIT15))->GetWindowText(tmp);
		d_val = _ttof(tmp);
		if (!spec_set_correct_params(g_spec_id, 1, m_nGrating, 6, &d_val)) {
			AfxMessageBox(_T("校正系数4设置错误."));
		}

		((CEdit*)GetDlgItem(IDC_EDIT16))->GetWindowText(tmp);
		d_val = _ttof(tmp);
		if (!spec_set_correct_params(g_spec_id, 1, m_nGrating, 7, &d_val)) {
			AfxMessageBox(_T("校正系数5设置错误."));
		}

		((CEdit*)GetDlgItem(IDC_EDIT17))->GetWindowText(tmp);
		d_val = _ttof(tmp);
		if (!spec_set_correct_params(g_spec_id, 1, m_nGrating, 8, &d_val)) {
			AfxMessageBox(_T("振幅设置错误."));
		}

		((CEdit*)GetDlgItem(IDC_EDIT18))->GetWindowText(tmp);
		d_val = _ttof(tmp);
		if (!spec_set_correct_params(g_spec_id, 1, m_nGrating, 9, &d_val)) {
			AfxMessageBox(_T("相位设置错误."));
		}

		((CEdit*)GetDlgItem(IDC_EDIT19))->GetWindowText(tmp);
		d_val = _ttof(tmp);
		if (!spec_set_correct_params(g_spec_id, 1, m_nGrating, 10, &d_val)) {
			AfxMessageBox(_T("频率设置错误."));
		}

		((CEdit*)GetDlgItem(IDC_EDIT20))->GetWindowText(tmp);
		n_val = _ttoi(tmp);
		if (!spec_set_correct_params(g_spec_id, 1, m_nGrating, 11, &n_val)) {
			AfxMessageBox(_T("起始电机步数设置错误."));
		}

		((CEdit*)GetDlgItem(IDC_EDIT21))->GetWindowText(tmp);
		s_val = _ttoi(tmp);
		if (!spec_set_correct_params(g_spec_id, 1, m_nGrating, 12, &s_val)) {
			AfxMessageBox(_T("偏置电机步数设置错误."));
		}

		((CEdit*)GetDlgItem(IDC_EDIT22))->GetWindowText(tmp);
		d_val = _ttof(tmp);
		if (!spec_set_correct_params(g_spec_id, 1, m_nGrating, 13, &d_val)) {
			AfxMessageBox(_T("刻线数设置错误."));
		}

		((CEdit*)GetDlgItem(IDC_EDIT23))->GetWindowText(tmp);
		d_val = _ttof(tmp);
		if (!spec_set_correct_params(g_spec_id, 1, m_nGrating, 14, &d_val)) {
			AfxMessageBox(_T("闪耀波长设置错误."));
		}
	}
	else {
		((CEdit*)GetDlgItem(IDC_EDIT1))->GetWindowText(tmp);
		f_val = _ttof(tmp);
		if (!spec_set_correct_params(g_spec_id, 1, m_nGrating, 0, &f_val)) {
			AfxMessageBox(_T("焦距设置错误."));
		}

		((CEdit*)GetDlgItem(IDC_EDIT10))->GetWindowText(tmp);
		f_val = _ttof(tmp);
		if (!spec_set_correct_params(g_spec_id, 1, m_nGrating, 1, &f_val)) {
			AfxMessageBox(_T("内置角设置错误."));
		}

		((CEdit*)GetDlgItem(IDC_EDIT11))->GetWindowText(tmp);
		f_val = _ttof(tmp);
		if (!spec_set_correct_params(g_spec_id, 1, m_nGrating, 2, &f_val)) {
			AfxMessageBox(_T("焦面倾斜角设置错误."));
		}

		((CEdit*)GetDlgItem(IDC_EDIT12))->GetWindowText(tmp);
		f_val = _ttof(tmp);
		if (!spec_set_correct_params(g_spec_id, 1, m_nGrating, 3, &f_val)) {
			AfxMessageBox(_T("P1设置错误."));
		}

		((CEdit*)GetDlgItem(IDC_EDIT13))->GetWindowText(tmp);
		f_val = _ttof(tmp);
		if (!spec_set_correct_params(g_spec_id, 1, m_nGrating, 4, &f_val)) {
			AfxMessageBox(_T("P2设置错误."));
		}

		((CEdit*)GetDlgItem(IDC_EDIT14))->GetWindowText(tmp);
		f_val = _ttof(tmp);
		if (!spec_set_correct_params(g_spec_id, 1, m_nGrating, 5, &f_val)) {
			AfxMessageBox(_T("P3设置错误."));
		}

		((CEdit*)GetDlgItem(IDC_EDIT15))->GetWindowText(tmp);
		f_val = _ttof(tmp);
		if (!spec_set_correct_params(g_spec_id, 1, m_nGrating, 6, &f_val)) {
			AfxMessageBox(_T("P4设置错误."));
		}

		((CEdit*)GetDlgItem(IDC_EDIT16))->GetWindowText(tmp);
		f_val = _ttof(tmp);
		if (!spec_set_correct_params(g_spec_id, 1, m_nGrating, 7, &f_val)) {
			AfxMessageBox(_T("P5设置错误."));
		}

		((CEdit*)GetDlgItem(IDC_EDIT17))->GetWindowText(tmp);
		f_val = _ttof(tmp);
		if (!spec_set_correct_params(g_spec_id, 1, m_nGrating, 8, &f_val)) {
			AfxMessageBox(_T("振幅设置错误."));
		}

		((CEdit*)GetDlgItem(IDC_EDIT18))->GetWindowText(tmp);
		f_val = _ttof(tmp);
		if (!spec_set_correct_params(g_spec_id, 1, m_nGrating, 9, &f_val)) {
			AfxMessageBox(_T("相位设置错误."));
		}

		((CEdit*)GetDlgItem(IDC_EDIT19))->GetWindowText(tmp);
		f_val = _ttof(tmp);
		if (!spec_set_correct_params(g_spec_id, 1, m_nGrating, 10, &f_val)) {
			AfxMessageBox(_T("频率设置错误."));
		}

		((CEdit*)GetDlgItem(IDC_EDIT20))->GetWindowText(tmp);
		n_val = _ttoi(tmp);
		if (!spec_set_correct_params(g_spec_id, 1, m_nGrating, 11, &n_val)) {
			AfxMessageBox(_T("起始电机步数设置错误."));
		}

		((CEdit*)GetDlgItem(IDC_EDIT21))->GetWindowText(tmp);
		n_val = _ttoi(tmp);
		if (!spec_set_correct_params(g_spec_id, 1, m_nGrating, 12, &n_val)) {
			AfxMessageBox(_T("偏置电机步数设置错误."));
		}

		((CEdit*)GetDlgItem(IDC_EDIT22))->GetWindowText(tmp);
		f_val = _ttof(tmp);
		if (!spec_set_correct_params(g_spec_id, 1, m_nGrating, 13, &f_val)) {
			AfxMessageBox(_T("刻线数设置错误."));
		}
	}
}


void CDlgCorrect::OnBnClickedButton17()
{
	// TODO: 在此添加控件通知处理程序代码
	
	short s_val;
	CString tmp;

	if (spec_get_correct_params(g_spec_id, 1, m_nGrating, 15, &s_val)) {
		tmp.Format(_T("%d"), s_val);
		((CEdit*)GetDlgItem(IDC_EDIT35))->SetWindowText(tmp);
	}

	if (spec_get_correct_params(g_spec_id, 1, m_nGrating, 16, &s_val)) {
		tmp.Format(_T("%d"), s_val);
		((CEdit*)GetDlgItem(IDC_EDIT36))->SetWindowText(tmp);
	}

	if (spec_get_correct_params(g_spec_id, 1, m_nGrating, 17, &s_val)) {
		tmp.Format(_T("%d"), s_val);
		((CEdit*)GetDlgItem(IDC_EDIT40))->SetWindowText(tmp);
	}

	if (spec_get_correct_params(g_spec_id, 1, m_nGrating, 18, &s_val)) {
		tmp.Format(_T("%d"), s_val);
		((CEdit*)GetDlgItem(IDC_EDIT41))->SetWindowText(tmp);
	}
}


void CDlgCorrect::OnBnClickedButton43()
{
	// TODO: 在此添加控件通知处理程序代码
	
	short s_val;
	CString tmp;

	((CEdit*)GetDlgItem(IDC_EDIT35))->GetWindowText(tmp);
	s_val = _ttoi(tmp);
	if (!spec_set_correct_params(g_spec_id, 1, m_nGrating, 15, &s_val)) {
		AfxMessageBox(_T("直出偏置设置错误."));
	}

	((CEdit*)GetDlgItem(IDC_EDIT36))->GetWindowText(tmp);
	s_val = _ttoi(tmp);
	if (!spec_set_correct_params(g_spec_id, 1, m_nGrating, 16, &s_val)) {
		AfxMessageBox(_T("侧出偏置设置错误."));
	}

	((CEdit*)GetDlgItem(IDC_EDIT40))->GetWindowText(tmp);
	s_val = _ttoi(tmp);
	if (!spec_set_correct_params(g_spec_id, 1, m_nGrating, 17, &s_val)) {
		AfxMessageBox(_T("侧出偏置设置错误."));
	}

	((CEdit*)GetDlgItem(IDC_EDIT41))->GetWindowText(tmp);
	s_val = _ttoi(tmp);
	if (!spec_set_correct_params(g_spec_id, 1, m_nGrating, 18, &s_val)) {
		AfxMessageBox(_T("侧出偏置设置错误."));
	}
}


void CDlgCorrect::OnBnClickedButton42()
{
	// TODO: 在此添加控件通知处理程序代码
	CFileDialog import(TRUE, 
		_T("BCK File(*.bck)|*.bck"), 
		NULL,
		OFN_HIDEREADONLY | OFN_OVERWRITEPROMPT,
		_T("Profile (*.ini)|*.ini|BCK File(*.bck)|*.bck||"), 
		this);

	if (import.DoModal() == IDOK) {
		CString path = import.GetPathName();
		CString ext = import.GetFileExt();

		if (ext.MakeLower() == _T("ini")) {
			if (!load_ini(path)) {
				AfxMessageBox(_T("文件内容错误!"));
				return;
			}
		}
		else if (ext.MakeLower() == _T("bck")) {
			if (!load_bck(path)) {
				AfxMessageBox(_T("文件内容错误!"));
				return;
			}
		}
		else {
			AfxMessageBox(_T("文件类型不支持!"));
			return;
		}
	}
}

bool CDlgCorrect::load_bck(CString path)
{
	auto path_tmp = to_string(path);

	ini_parser ini;
	ini.init(to_string(path));

	std::string id = ini.get_string("General", "IDSTRING");
	std::string s_ver = ini.get_string("General", "SVERNO");
	std::string i_ver = ini.get_string("General", "IVERNO");
	std::string dom = ini.get_string("General", "DOM");
	std::string date = ini.get_string("General", "DATE");

	char buff[128] = { 0 };
	sprintf(buff, "IDSTRING:%s\r\nSVERNO:%s\r\nIVERNO:%s\r\nDOM:%s\r\nDATE:%s\r\n", id.c_str(), s_ver.c_str(), i_ver.c_str(), dom.c_str(), date.c_str());
	if (MessageBox(CString(buff), _T("确认信息"), MB_OKCANCEL | MB_ICONWARNING) == IDCANCEL) return true;

	//general
	m_fFoclen = ini.get_double("General", "FOCLEN");
	m_fAngdev = ini.get_double("General", "ANGDEV");
	m_fFoctlt = ini.get_double("General", "FOCTLT");

	//wavelength
	m_fPoly1 = ini.get_double("Wavelength", "POLY1");
	m_fPoly2 = ini.get_double("Wavelength", "POLY2");
	m_fPoly3 = ini.get_double("Wavelength", "POLY3");
	m_fPoly4 = ini.get_double("Wavelength", "POLY4");
	m_fPoly5 = ini.get_double("Wavelength", "POLY5");

	m_fAmp = ini.get_double("Wavelength", "SINAMPLITUDE");
	m_fPhase = ini.get_double("Wavelength", "SINPHASE");
	m_fFreq = ini.get_double("Wavelength", "SINFREQUENCY");

	m_sFront = ini.get_double("Wavelength", "DETECTOROFFSET1");
	m_sSide = ini.get_double("Wavelength", "DETECTOROFFSET2");

	char key[64] = { 0 };
	sprintf(key, "GRATSTART%d", m_nGrating);
	m_nStart = ini.get_int("Wavelength", key);
	
	sprintf(key, "GRATOFFSET%d", m_nGrating);
	m_sOffset = ini.get_double("Wavelength", key);
	
	sprintf(key, "GRATLINES%d", m_nGrating);
	m_fLines = ini.get_double("Wavelength", key);

	sprintf(key, "GRATBLAZE%d", m_nGrating);
	m_fBlaze = ini.get_double("Wavelength", key);

	UpdateData(FALSE);
	return true;
}

bool CDlgCorrect::save_bck(CString path)
{
	UpdateData(TRUE);

	ini_parser ini;
	ini.init(to_string(path));

	//general
	ini.set_double("General", "FOCLEN", m_fFoclen);
	ini.set_double("General", "ANGDEV", m_fAngdev);
	ini.set_double("General", "FOCTLT", m_fFoctlt);
	//
	ini.set_string("General", "IDSTRING","Zolix Technology");
	ini.set_string("General", "SVERNO","1.3.16");
	ini.set_string("General", "IVERNO","SR-1912");
	ini.set_string("General", "DOM", "02/08/2007");

	auto time_now = std::chrono::system_clock::now();
	auto tt = std::chrono::system_clock::to_time_t(time_now);
	struct tm* ptm = localtime(&tt);

	char date[20] = { 0 };
	sprintf(date, "%02d/%02d/%d", (int)ptm->tm_mday, (int)ptm->tm_mon + 1,(int)ptm->tm_year + 1900);
	ini.set_string("General", "DATE", date);

	//wavelength
	ini.set_double("Wavelength", "POLY1",m_fPoly1);
	ini.set_double("Wavelength", "POLY2",m_fPoly2);
	ini.set_double("Wavelength", "POLY3",m_fPoly3);
	ini.set_double("Wavelength", "POLY4",m_fPoly4);
	ini.set_double("Wavelength", "POLY5",m_fPoly5);
	ini.set_double("Wavelength", "SINAMPLITUDE",m_fAmp);
	ini.set_double("Wavelength", "SINPHASE",m_fPhase);
	ini.set_double("Wavelength", "SINFREQUENCY",m_fFreq);

	//////////////////////////////////////////////////////////////////////////
	ini.set_int("Wavelength", "ENABLECALIBRATION", 1);

	float wave = 0;
	spec_get_curr_wave(g_spec_id, &wave);

	ini.set_double("Wavelength", "CURRENTWAVELENGTH", wave);

	ini.set_double("Wavelength", "DETECTOROFFSET1", m_sFront);
	ini.set_double("Wavelength", "DETECTOROFFSET2", m_sSide);

	ini.set_double("Wavelength", "NOOFTURRETS", 3);
	ini.set_double("Wavelength", "ACTIVETURRET", m_nTurret);

	char buff[20] = { 0 };
	for (int i=1;i<=3;i++)
	{
		sprintf(buff, "GRATSTART%d", i);
		ini.set_int("Wavelength", buff, m_nStart);

		sprintf(buff, "GRATOFFSET%d", i);
		ini.set_double("Wavelength", "GRATOFFSET1", m_sOffset);

		sprintf(buff, "GRATLINES%d", i);
		ini.set_double("Wavelength", "GRATLINES1", m_fLines);

		sprintf(buff, "GRATBLAZE%d", i);
		ini.set_double("Wavelength", "GRATBLAZE1", m_fBlaze);
	}

	int groove = 0;
	long blaze = 0;

	short grating_count = 3;
	if (spec_get_grating_info(g_spec_id, 3, &groove, &blaze)) {
		if (groove <= 0 || blaze <= 0) {
			grating_count = 2;
		}
	}

	ini.set_double("Wavelength", "NOOFGRATINGS", grating_count);

	//filter
	ini.set_string("Filter", "FILTERSTRINGS1", "Filter 1");
	ini.set_string("Filter", "FILTERSTRINGS2", "Filter 2");
	ini.set_string("Filter", "FILTERSTRINGS3", "Filter 3");
	ini.set_string("Filter", "FILTERSTRINGS4", "Filter 4");
	ini.set_string("Filter", "FILTERSTRINGS5", "Filter 5");
	ini.set_string("Filter", "FILTERSTRINGS6", "Filter 6");

	return true;
}

bool CDlgCorrect::load_ini(CString path)
{
	ini_parser ini;
	ini.init(to_string(path));

	std::string id = ini.get_string("General", "Manufacturers");
	std::string date = ini.get_string("General", "DATE");
	std::string sn = ini.get_string("General", "SerialNumber");
	std::string ver = ini.get_string("General", "Version");

	char buff[128] = { 0 };
	sprintf(buff, "Manufacturers:%s\r\nDATE:%s\r\nSerialNumber:%s\r\nVersion:%s", id.c_str(), date.c_str(), sn.c_str(), ver.c_str());
	if (MessageBox(CString(buff), _T("确认信息"), MB_OKCANCEL | MB_ICONWARNING) == IDCANCEL) return true;

	char turret[64] = {0};
	sprintf(turret, "Turret%d", m_nTurret);

	//general
	sprintf(buff, "G%dFOCLEN", m_nGrating);
	m_fFoclen = ini.get_double(turret, buff);

	sprintf(buff, "G%dANGDEV", m_nGrating);
	m_fAngdev = ini.get_double(turret, buff);

	sprintf(buff, "G%dFOCTLT", m_nGrating);
	m_fFoctlt = ini.get_double(turret, buff);

	//wavelength
	sprintf(buff, "G%dPOLY1", m_nGrating);
	m_fPoly1 = ini.get_double(turret, buff);

	sprintf(buff, "G%dPOLY2", m_nGrating);
	m_fPoly2 = ini.get_double(turret, buff);

	sprintf(buff, "G%dPOLY3", m_nGrating);
	m_fPoly3 = ini.get_double(turret, buff);

	sprintf(buff, "G%dPOLY4", m_nGrating);
	m_fPoly4 = ini.get_double(turret, buff);

	sprintf(buff, "G%dPOLY5", m_nGrating);
	m_fPoly5 = ini.get_double(turret, buff);

	sprintf(buff, "G%dSINAMPLITUDE", m_nGrating);
	m_fAmp = ini.get_double(turret, buff);

	sprintf(buff, "G%dSINPHASE", m_nGrating);
	m_fPhase = ini.get_double(turret, buff);

	sprintf(buff, "G%dSINFREQUENCY", m_nGrating);
	m_fFreq = ini.get_double(turret, buff);

	m_sFront = ini.get_double(turret, "FrontOffset");
	m_sSide = ini.get_double(turret, "SideOffset");

	sprintf(buff, "G%dStart", m_nGrating);
	m_nStart = ini.get_int(turret, buff);

	sprintf(buff, "G%dOffset", m_nGrating);
	m_sOffset = ini.get_double(turret, buff);

	sprintf(buff, "G%dLines", m_nGrating);
	m_fLines = ini.get_double(turret, buff);

	sprintf(buff, "G%dBlaze", m_nGrating);
	m_fBlaze = ini.get_double(turret, buff);

	UpdateData(FALSE);
	return true;
}

bool CDlgCorrect::save_ini(CString path)
{
	UpdateData(TRUE);

	ini_parser ini;
	ini.init(to_string(path));

	spec_info info;
	spec_get_dev_info(g_spec_id, &info);

	ini.set_string("General", "Manufacturers", info.manufacturer);
	ini.set_string("General", "DATE", info.date);
	ini.set_string("General", "SerialNumber", info.sn);
	ini.set_string("General", "Version", info.firmware_ver + 1);

	char turret[64] = { 0 };
	sprintf(turret, "Turret%d", m_nTurret);

	char buff[64] = { 0 };
	//general
	ini.set_double(turret, "FrontOffset", m_sFront);
	ini.set_double(turret, "SideOffset", m_sSide);

	sprintf(buff, "G%dFOCLEN", m_nGrating);
	ini.set_double(turret, buff, m_fFoclen);

	sprintf(buff, "G%dANGDEV", m_nGrating);
	ini.set_double(turret, buff, m_fAngdev);

	sprintf(buff, "G%dFOCTLT", m_nGrating);
	ini.set_double(turret, buff, m_fFoctlt);

	//wavelength
	sprintf(buff, "G%dPOLY1", m_nGrating);
	ini.set_double(turret, buff, m_fPoly1);

	sprintf(buff, "G%dPOLY2", m_nGrating);
	ini.set_double(turret, buff, m_fPoly2);

	sprintf(buff, "G%dPOLY3", m_nGrating);
	ini.set_double(turret, buff, m_fPoly3);

	sprintf(buff, "G%dPOLY4", m_nGrating);
	ini.set_double(turret, buff, m_fPoly4);

	sprintf(buff, "G%dPOLY5", m_nGrating);
	ini.set_double(turret, buff, m_fPoly5);

	sprintf(buff, "G%dSINAMPLITUDE", m_nGrating);
	ini.set_double(turret, buff, m_fAmp);

	sprintf(buff, "G%dSINPHASE", m_nGrating);
	ini.set_double(turret, buff, m_fPhase);

	sprintf(buff, "G%dSINFREQUENCY", m_nGrating);
	ini.set_double(turret, buff, m_fFreq);

	sprintf(buff, "G%dStart", m_nGrating);
	ini.set_int(turret, buff, m_nStart);

	sprintf(buff, "G%dOffset", m_nGrating);
	ini.set_double(turret, buff, m_sOffset);

	sprintf(buff, "G%dLines", m_nGrating);
	ini.set_double(turret, buff, m_fLines);

	sprintf(buff, "G%dBlaze", m_nGrating);
	ini.set_double(turret, buff, m_fBlaze);

	return true;
}

void CDlgCorrect::OnBnClickedButton52()
{
	// TODO: 在此添加控件通知处理程序代码
	CFileDialog expo(FALSE,
		_T("BCK File(*.bck)|*.bck"),
		NULL,
		OFN_HIDEREADONLY | OFN_OVERWRITEPROMPT,
		_T("Profile (*.ini)|*.ini|BCK File(*.bck)|*.bck||"),
		this);

	if (expo.DoModal() == IDOK) {
		CString path = expo.GetPathName();
		CString ext = expo.GetFileExt();

		if (ext.MakeLower() == _T("ini")) {
			if (!save_ini(path)) {
				AfxMessageBox(_T("文件内容错误!"));
				return;
			}
		}
		else if (ext.MakeLower() == _T("bck")) {
			if (!save_bck(path)) {
				AfxMessageBox(_T("文件内容错误!"));
				return;
			}
		}
		else {
			AfxMessageBox(_T("文件类型不支持!"));
			return;
		}
	}
}


void CDlgCorrect::OnBnClickedButton3()
{
	// TODO: 在此添加控件通知处理程序代码
	CString str;
	GetDlgItem(IDC_EDIT24)->GetWindowText(str);

	float wave = _ttof(str);
	float step = spec_wave_to_step(g_spec_id, wave);

	str.Format(_T("%f"), step);
	GetDlgItem(IDC_EDIT25)->SetWindowText(str);
}


void CDlgCorrect::OnBnClickedButton15()
{
	// TODO: 在此添加控件通知处理程序代码
	CString str;

	GetDlgItem(IDC_EDIT29)->GetWindowText(str);
	int count = _ttoi(str);

	GetDlgItem(IDC_EDIT30)->GetWindowText(str);
	int width = _ttoi(str);

	GetDlgItem(IDC_EDIT_CENT_WAVE)->GetWindowText(str);
	float cent_wave = _ttof(str);

	int g = 0, t = 0;
	spec_get_turret(g_spec_id, &t);
	spec_get_grating(g_spec_id, &g);

	auto result = std::make_unique<float[]>(count);
	spec_pixels_to_waves(g_spec_id, t, g, cent_wave, width, count, 1, result.get());

	auto ptr = (CListCtrl*)GetDlgItem(IDC_LIST1);
	ptr->DeleteAllItems();

	for (int i=0;i<count;i++)
	{
		ptr->InsertItem(i, _T(""));
		
		str.Format(_T("%d"), i);
		ptr->SetItemText(i, 0, str);

		str.Format(_T("%g"), result[i]);
		ptr->SetItemText(i, 1, str);
	}
}


void CDlgCorrect::OnBnClickedButton16()
{
	// TODO: 在此添加控件通知处理程序代码
	CFileDialog expo(FALSE,
		_T("BCK File(*.bck)|*.bck"),
		NULL,
		OFN_HIDEREADONLY | OFN_OVERWRITEPROMPT,
		_T("文本文档 (*.txt)|*.txt||"),
		this);

	if (expo.DoModal() == IDOK) {
		CString path = expo.GetPathName();
	
		std::ofstream  writer;
		writer.open(path, std::ios::out);
		if (!writer.is_open())
		{
			AfxMessageBox(_T("文件打开失败."));
			return;
		}

		auto ptr = (CListCtrl*)GetDlgItem(IDC_LIST1);
		auto count = ptr->GetItemCount();

		for (int i = 0; i < count; i++)
		{
			auto pixel = ptr->GetItemText(i, 0);
			auto wave = ptr->GetItemText(i, 1);
			
			writer << to_string(pixel) << "\t" << to_string(wave) << std::endl;
			writer.flush();
		}

		writer.close();
	}
}


void CDlgCorrect::OnBnClickedButton18()
{
	// TODO: 在此添加控件通知处理程序代码
	
	CString str;
	GetDlgItem(IDC_EDIT25)->GetWindowText(str);

	float steps = _ttof(str);
	if (!spec_move_to_steps(g_spec_id, steps)) {
		AfxMessageBox(_T("Move to steps failed."));
	}
}


BOOL CDlgCorrect::PreTranslateMessage(MSG* pMsg)
{
	// TODO: 在此添加专用代码和/或调用基类
	if (pMsg->message == WM_KEYDOWN) {
		if (pMsg->wParam == VK_RETURN || pMsg->wParam == VK_ESCAPE) {
			return TRUE;
		}
	}
	return CDialogEx::PreTranslateMessage(pMsg);
}
