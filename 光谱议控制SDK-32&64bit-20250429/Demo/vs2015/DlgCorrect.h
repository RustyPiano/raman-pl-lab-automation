#pragma once
#include <string>

/************************************************************************/
/* 设置校正系数
/* code:
/*			00 - 谱仪焦距				float
/*			01 - 谱仪内置角			    float
/*			02 - 焦面倾斜角			    float
/*			03 - 光栅校正系数1			float
/*			04 - 光栅校正系数2			float
/*			05 - 光栅校正系数3			float
/*			06 - 光栅校正系数4			float
/*			07 - 光栅校正系数5			float
/*			08 - 余弦校正系数 - 振幅	float
/*			09 - 余弦校正系数 - 相位	float
/*			10 - 余弦校正系数 - 频率	short
/*			11 - 光栅起始电机步数		int
/*			12 - 光栅偏置电机步数		short
/*			13 - 光栅刻线				float
/*			14 - 光栅闪耀波长			short
/*			15 - 直出偏置				short
/*			16 - 侧出偏置				short
/************************************************************************/

// CDlgCorrect 对话框

class CDlgCorrect : public CDialogEx
{
	DECLARE_DYNAMIC(CDlgCorrect)

public:
	CDlgCorrect(CWnd* pParent = NULL);   // 标准构造函数
	virtual ~CDlgCorrect();

// 对话框数据
#ifdef AFX_DESIGN_TIME
	enum { IDD = IDD_DIALOG_CORRECT };
#endif

protected:
	virtual void DoDataExchange(CDataExchange* pDX);    // DDX/DDV 支持

	DECLARE_MESSAGE_MAP()
private:
	int m_nTurret;
	int m_nGrating;

	bool load_bck(CString path);
	bool save_bck(CString path);

	bool load_ini(CString path);
	bool save_ini(CString path);
public:
	virtual BOOL OnInitDialog();

	afx_msg void OnShowWindow(BOOL bShow, UINT nStatus);
	afx_msg void OnBnClickedButton1();
	afx_msg void OnBnClickedButton2();
	afx_msg void OnBnClickedButton17();
	afx_msg void OnBnClickedButton43();
	afx_msg void OnBnClickedButton42();
	afx_msg void OnBnClickedButton52();
	float m_fFoclen;
	float m_fAngdev;
	float m_fFoctlt;
	double m_fPoly1;
	double m_fPoly2;
	double m_fPoly3;
	double m_fPoly4;
	double m_fPoly5;
	double m_fAmp;
	double m_fPhase;
	double m_fFreq;
	int m_nStart;
	short m_sOffset;
	double m_fLines;
	double m_fBlaze;
	short m_sFront;
	short m_sSide;
	std::string m_ver;
	afx_msg void OnBnClickedButton3();
	afx_msg void OnBnClickedButton15();
	afx_msg void OnBnClickedButton16();
	afx_msg void OnBnClickedButton18();
	virtual BOOL PreTranslateMessage(MSG* pMsg);
};
