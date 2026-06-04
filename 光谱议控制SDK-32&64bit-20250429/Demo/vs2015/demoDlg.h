
// demoDlg.h : 头文件
//

#pragma once
#include "afxwin.h"

// CdemoDlg 对话框
class CdemoDlg : public CDialogEx
{
// 构造
public:
	CdemoDlg(CWnd* pParent = NULL);	// 标准构造函数

// 对话框数据
#ifdef AFX_DESIGN_TIME
	enum { IDD = IDD_DEMO_DIALOG };
#endif

	protected:
	virtual void DoDataExchange(CDataExchange* pDX);	// DDX/DDV 支持

public:
	void update_status();

// 实现
protected:
	HICON m_hIcon;

	// 生成的消息映射函数
	virtual BOOL OnInitDialog();
	afx_msg void OnPaint();
	afx_msg HCURSOR OnQueryDragIcon();
	DECLARE_MESSAGE_MAP()

public:
	afx_msg void OnBnClickedButton3();
	afx_msg void OnClose();
	afx_msg void OnBnClickedButton1();
	afx_msg void OnBnClickedButton2();
	// 谱仪当前光栅
	int m_nGrating;
	int m_nEntrance;
	int m_nExit;
	int m_nFilter;
	bool m_bStop;
	bool m_bHipers;

	CButton m_btFresh;
	afx_msg void OnBnClickedButton26();
	afx_msg void OnBnClickedButton13();
	afx_msg void OnBnClickedRadio1();
	afx_msg void OnBnClickedRadio3();
	afx_msg void OnBnClickedRadio2();
	afx_msg void OnBnClickedRadio10();
	afx_msg void OnBnClickedRadio12();
	afx_msg void OnBnClickedRadio13();
	afx_msg void OnBnClickedRadio15();
	afx_msg void OnBnClickedButton4();
	afx_msg void OnBnClickedButton5();
	afx_msg void OnBnClickedButton40();
	afx_msg void OnBnClickedCheck1();
	afx_msg void OnBnClickedRadio4();
	afx_msg void OnBnClickedRadio5();
	afx_msg void OnBnClickedRadio6();
	afx_msg void OnBnClickedRadio7();
	afx_msg void OnBnClickedRadio8();
	afx_msg void OnBnClickedRadio9();
	afx_msg void OnBnClickedButton6();
	afx_msg void OnBnClickedButton7();
	afx_msg void OnBnClickedButton8();
	afx_msg void OnBnClickedButton42();
	afx_msg void OnBnClickedButton44();
	afx_msg void OnBnClickedButton45();
	afx_msg void OnBnClickedButton49();
	afx_msg void OnBnClickedButton47();
	afx_msg void OnBnClickedButton51();
	afx_msg void OnBnClickedCheck5();
	afx_msg void OnBnClickedCheck11();
	virtual BOOL PreTranslateMessage(MSG* pMsg);
	afx_msg void OnBnClickedButton50();
	afx_msg void OnBnClickedButton46();
	afx_msg void OnBnClickedButton48();
	afx_msg void OnBnClickedButton52();
	afx_msg void OnBnClickedButton9();
	afx_msg void OnBnClickedButton53();
	afx_msg void OnBnClickedButton54();
	afx_msg void OnCbnSelchangeCombo2();
	afx_msg void OnCbnSelchangeCombo5();
	afx_msg void OnBnClickedButton23();
	afx_msg void OnBnClickedButton57();
	afx_msg void OnBnClickedButton56();
	afx_msg void OnBnClickedButton58();
	afx_msg void OnCbnSelchangeCombo3();
	afx_msg void OnBnClickedButton10();
	afx_msg void OnBnClickedButton55();
};
