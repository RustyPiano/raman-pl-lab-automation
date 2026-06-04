#pragma once
// CDlgAdvance 对话框

class CDlgAdvance : public CDialogEx
{
	DECLARE_DYNAMIC(CDlgAdvance)

public:
	CDlgAdvance(CWnd* pParent = NULL);   // 标准构造函数
	virtual ~CDlgAdvance();

// 对话框数据
#ifdef AFX_DESIGN_TIME
	enum { IDD = IDD_DIALOG_ADVANCE };
#endif

protected:
	virtual void DoDataExchange(CDataExchange* pDX);    // DDX/DDV 支持

	DECLARE_MESSAGE_MAP()
public:
	afx_msg void OnShowWindow(BOOL bShow, UINT nStatus);
	afx_msg void OnBnClickedButton1();
	afx_msg void OnBnClickedButton2();

private:
	bool m_bHipers;
	void update_status();
	void update_grating_info();
	void update_filter_info();

public:
	afx_msg void OnBnClickedButton26();
	afx_msg void OnBnClickedButton27();
	afx_msg void OnBnClickedButton14();
	afx_msg void OnBnClickedButton20();
	afx_msg void OnBnClickedButton16();
	afx_msg void OnBnClickedButton22();
	afx_msg void OnBnClickedButton17();
	afx_msg void OnBnClickedButton23();
	afx_msg void OnBnClickedButton18();
	afx_msg void OnBnClickedButton24();
	afx_msg void OnBnClickedButton19();
	afx_msg void OnBnClickedButton28();
	afx_msg void OnBnClickedButton34();
	afx_msg void OnBnClickedButton29();
	afx_msg void OnBnClickedButton35();
	afx_msg void OnBnClickedButton30();
	afx_msg void OnBnClickedButton36();
	afx_msg void OnBnClickedButton31();
	afx_msg void OnBnClickedButton37();
	afx_msg void OnBnClickedButton32();
	afx_msg void OnBnClickedButton38();
	afx_msg void OnBnClickedButton33();
	afx_msg void OnBnClickedButton39();
	afx_msg void OnBnClickedCheck2();
	afx_msg void OnBnClickedCheck4();
	afx_msg void OnBnClickedCheck3();
	afx_msg void OnBnClickedCheck7();
	afx_msg void OnBnClickedCheck6();
	afx_msg void OnBnClickedCheck8();
	afx_msg void OnBnClickedCheck5();
	afx_msg void OnBnClickedCheck10();
	afx_msg void OnBnClickedCheck9();
	afx_msg void OnCbnSelchangeCombo1();
	afx_msg void OnCbnSelchangeCombo4();
	virtual BOOL PreTranslateMessage(MSG* pMsg);
};
