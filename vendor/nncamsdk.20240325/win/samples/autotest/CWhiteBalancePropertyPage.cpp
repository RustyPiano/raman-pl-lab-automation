#include "stdafx.h"
#include "global.h"
#include "AutoTest.h"
#include "CWhiteBalancePropertyPage.h"

CWhiteBalancePropertyPage::CWhiteBalancePropertyPage()
	: CPropertyPage(IDD_PROPERTY_WHITE_BALANCE)
{
}

void CWhiteBalancePropertyPage::OnWhiteBalance()
{
	if (GetSafeHwnd())
	{
		int temp = 0, tint = 0;
		Nncam_get_TempTint(g_hcam, &temp, &tint);
		SetTempValue(temp);
		SetTintValue(tint);
	}
}

void CWhiteBalancePropertyPage::SetTempValue(int value)
{
	((CSliderCtrl*)GetDlgItem(IDC_SLIDER_TEMP))->SetPos(value);
	SetDlgItemInt(IDC_STATIC_TEMP, value);
}

void CWhiteBalancePropertyPage::SetTintValue(int value)
{
	((CSliderCtrl*)GetDlgItem(IDC_SLIDER_TINT))->SetPos(value);
	SetDlgItemInt(IDC_STATIC_TINT, value);
}

BEGIN_MESSAGE_MAP(CWhiteBalancePropertyPage, CPropertyPage)
	ON_WM_HSCROLL()
	ON_BN_CLICKED(IDC_BUTTON_WHITE_BALANCE, &CWhiteBalancePropertyPage::OnBnClickedButtonWhiteBalance)
END_MESSAGE_MAP()

BOOL CWhiteBalancePropertyPage::OnInitDialog()
{
	CPropertyPage::OnInitDialog();

	((CSliderCtrl*)GetDlgItem(IDC_SLIDER_TEMP))->SetRange(NNCAM_TEMP_MIN, NNCAM_TEMP_MAX);
	SetTempValue(NNCAM_TEMP_DEF);
	((CSliderCtrl*)GetDlgItem(IDC_SLIDER_TINT))->SetRange(NNCAM_TINT_MIN, NNCAM_TINT_MAX);
	SetTintValue(NNCAM_TINT_DEF);

	return TRUE;
}

void CWhiteBalancePropertyPage::OnHScroll(UINT nSBCode, UINT nPos, CScrollBar* pScrollBar)
{
	int curTemp = 0, curTint = 0;
	if (pScrollBar == GetDlgItem(IDC_SLIDER_TEMP))
	{
		Nncam_get_TempTint(g_hcam, &curTemp, &curTint);
		int temp = ((CSliderCtrl*)GetDlgItem(IDC_SLIDER_TEMP))->GetPos();
		if (temp != curTemp)
		{
			Nncam_put_TempTint(g_hcam, temp, curTint);
			SetDlgItemInt(IDC_STATIC_TEMP, temp);
		}
	}
	else if (pScrollBar == GetDlgItem(IDC_SLIDER_TINT))
	{
		Nncam_get_TempTint(g_hcam, &curTemp, &curTint);
		int tint = ((CSliderCtrl*)GetDlgItem(IDC_SLIDER_TINT))->GetPos();
		if (tint != curTint)
		{
			Nncam_put_TempTint(g_hcam, curTemp, tint);
			SetDlgItemInt(IDC_STATIC_TINT, tint);
		}
	}

	CPropertyPage::OnHScroll(nSBCode, nPos, pScrollBar);
}

void CWhiteBalancePropertyPage::OnBnClickedButtonWhiteBalance()
{
	Nncam_AwbOnce(g_hcam, nullptr, nullptr);
}
