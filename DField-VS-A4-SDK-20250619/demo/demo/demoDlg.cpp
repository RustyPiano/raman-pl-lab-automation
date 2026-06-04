
// demoDlg.cpp : 实现文件
//

#include "stdafx.h"
#include "demo.h"
#include "demoDlg.h"
#include "afxdialogex.h"

#ifdef _DEBUG
#define new DEBUG_NEW
#endif

#include <algorithm>
#include <vector>

// CdemoDlg 对话框
#include "dfield-vs-a4.h"

#include "CImg.h"
using namespace cimg_library;

CdemoDlg::CdemoDlg(CWnd* pParent /*=NULL*/)
	: CDialogEx(IDD_DEMO_DIALOG, pParent)
	, _exp_ms(0)
	, _gain(0)
	, _mode(0)
	, _cooling(0)
	, _current(0)
{
	m_hIcon = AfxGetApp()->LoadIcon(IDR_MAINFRAME);
}

void CdemoDlg::DoDataExchange(CDataExchange* pDX)
{
	CDialogEx::DoDataExchange(pDX);
	DDX_Text(pDX, IDC_EDIT1, _exp_ms);
	DDX_CBIndex(pDX, IDC_COMBO1, _gain);
	DDX_CBIndex(pDX, IDC_COMBO2, _mode);
	DDX_Text(pDX, IDC_EDIT5, _cooling);
	DDX_Text(pDX, IDC_EDIT4, _current);
	DDX_Control(pDX, IDC_TCHART1, _chart);
}

BEGIN_MESSAGE_MAP(CdemoDlg, CDialogEx)
	ON_WM_PAINT()
	ON_WM_QUERYDRAGICON()
	ON_BN_CLICKED(IDC_BUTTON1, &CdemoDlg::OnBnClickedButton1)
	ON_WM_TIMER()
	ON_BN_CLICKED(IDC_BUTTON2, &CdemoDlg::OnBnClickedButton2)
	ON_BN_CLICKED(IDC_BUTTON6, &CdemoDlg::OnBnClickedButton6)
	ON_BN_CLICKED(IDC_BUTTON3, &CdemoDlg::OnBnClickedButton3)
	ON_BN_CLICKED(IDC_BUTTON4, &CdemoDlg::OnBnClickedButton4)
	ON_BN_CLICKED(IDC_BUTTON5, &CdemoDlg::OnBnClickedButton5)
	ON_BN_CLICKED(IDC_BUTTON7, &CdemoDlg::OnBnClickedButton7)
	ON_BN_CLICKED(IDC_BUTTON8, &CdemoDlg::OnBnClickedButton8)
END_MESSAGE_MAP()


// CdemoDlg 消息处理程序

BOOL CdemoDlg::OnInitDialog()
{
	CDialogEx::OnInitDialog();

	// 设置此对话框的图标。  当应用程序主窗口不是对话框时，框架将自动
	//  执行此操作
	SetIcon(m_hIcon, TRUE);			// 设置大图标
	SetIcon(m_hIcon, FALSE);		// 设置小图标

	// TODO: 在此添加额外的初始化代码
	_opened = false;

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



void CdemoDlg::OnBnClickedButton1()
{
	// TODO: 在此添加控件通知处理程序代码
	_opened = a4_open();
	if (!_opened) {
		AfxMessageBox(_T("连接失败."));
		return;
	}

	a4_get_gain(&_gain);
	a4_get_exposure(&_exp_ms);

	_mode = 0;
	a4_set_read_mode(_mode);

	int bin_x = 1, bin_y = 1;
	a4_get_bin(&bin_x, &bin_y);
	((CComboBox*)GetDlgItem(IDC_COMBO3))->SetCurSel(log10(bin_x) / log10(2));

	a4_get_cooling_temp(&_cooling);
	a4_get_current_temp(&_current);

	SetTimer(1001, 300, NULL);
	UpdateData(FALSE);
}


void CdemoDlg::OnTimer(UINT_PTR nIDEvent)
{
	// TODO: 在此添加消息处理程序代码和/或调用默认值
	switch (nIDEvent)
	{
	case 1001: {
		float temp = .0f;
		a4_get_current_temp(&temp);

		CString str;
		str.Format(_T("%g"), temp);
		GetDlgItem(IDC_EDIT4)->SetWindowText(str);
	} break;
	}


	CDialogEx::OnTimer(nIDEvent);
}


void CdemoDlg::OnBnClickedButton2()
{
	// TODO: 在此添加控件通知处理程序代码
	if (_busy) {
		AfxMessageBox(_T("先停止采集."));
		return;
	}

	a4_close();
	_opened = false;
}


void CdemoDlg::OnBnClickedButton6()
{
	// TODO: 在此添加控件通知处理程序代码
	UpdateData(TRUE);

	if (!_opened) {
		AfxMessageBox(_T("相机未连接."));
		return;
	}

	a4_set_gain(_gain);
}


void CdemoDlg::OnBnClickedButton3()
{
	// TODO: 在此添加控件通知处理程序代码
	UpdateData(TRUE);

	if (!_opened) {
		AfxMessageBox(_T("相机未连接."));
		return;
	}

	a4_set_exposure(_exp_ms);
}


void CdemoDlg::OnBnClickedButton4()
{
	// TODO: 在此添加控件通知处理程序代码
	if (!_opened) {
		AfxMessageBox(_T("相机未连接."));
		return;
	}

	int bin_x = ((CComboBox*)GetDlgItem(IDC_COMBO3))->GetCurSel();
	a4_set_bin(pow(2, bin_x), 1);
}


void CdemoDlg::OnBnClickedButton5()
{
	// TODO: 在此添加控件通知处理程序代码
	UpdateData(TRUE);

	if (!_opened) {
		AfxMessageBox(_T("相机未连接."));
		return;
	}

	a4_set_read_mode(_mode);
}


void CdemoDlg::OnBnClickedButton7()
{
	// TODO: 在此添加控件通知处理程序代码
	UpdateData(TRUE);

	if (!_opened) {
		AfxMessageBox(_T("相机未连接."));
		return;
	}

	a4_set_cooling_temp(_cooling);
}


void CdemoDlg::OnBnClickedButton8()
{
	// TODO: 在此添加控件通知处理程序代码
	UpdateData(TRUE);

	int w = 1, h = 1;
	a4_get_detector_size(&w, &h);

	int bin_x = ((CComboBox*)GetDlgItem(IDC_COMBO3))->GetCurSel();

	size_t size = w / pow(2, bin_x);
	if (_mode == 1) size *= h;

	a4_set_trigger_mode(1);

	std::vector<long> buff(size, 0);
	a4_single_capture(&(buff[0]), size);

	if (_mode == 1) {
		long max = *std::max_element(buff.begin(), buff.end());
		long min = *std::min_element(buff.begin(), buff.end());

		CImg<float> img((w / pow(2, bin_x)), h, 1, 1, 0);

		//fill the img window in black
		img.fill(0);

		int i_counter = 0;
		for (int y = 0; y < h; ++y)
		{
			for (int x = 0; x < (w / pow(2, bin_x)); x++)
			{
				unsigned char _ucp_grayScale[] = { 255,255,255 };         //define the colour white
				float f_intensity = (((buff[i_counter] - min) * 1.0 / (65535 - min) * 255));	//Calculate pixel intensity
				img.draw_point(x, y, _ucp_grayScale, f_intensity);           //Draw Pixel
				i_counter++;
			}
		}
		img.display("Image");
	}
	else {
		_chart.Series(0).Clear();
		for (int i = 0; i < size; i++) {
			_chart.Series(0).AddXY(i + 1, buff[i], NULL, _chart.Series(0).GetColor());
		}

		_chart.Repaint();
	}
}
