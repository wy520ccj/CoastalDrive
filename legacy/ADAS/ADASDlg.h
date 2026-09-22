
#pragma once
#include "CSimulationEngine.h"
#include <fstream>

#define WM_SHOW_CRASH_DIALOG (WM_APP + 1)

class CADASDlg : public CDialogEx
{
public:
    CADASDlg(CWnd* pParent = nullptr);
    ~CADASDlg();

#ifdef AFX_DESIGN_TIME
    enum { IDD = IDD_ADAS_DIALOG };
#endif

protected:
    virtual void DoDataExchange(CDataExchange* pDX);

private:
    CSimulationEngine m_engine;
    bool m_bCrashDialogShown;
    bool m_bW_KeyDown;
    bool m_bS_KeyDown;
    DWORD m_dwLastBeepTime;
    std::ofstream m_logFile;

    void UpdateUIFromEngine();
    void ResetSimulation();

    void DrawAnimeStyleCar(CDC& dc, int x, int y, int width, int height, COLORREF carColor, bool isOurCar);
    void DrawRoadSideScenery(CDC& dc);
    void DrawMovingClouds(CDC& dc, const CRect& skyRect, double ourSpeed_ms, double scenarioTime);
    void DrawDistantBuildings(CDC& dc, COLORREF baseColor);
    void DrawDynamicTreeRows(CDC& dc, int startX, int endX, COLORREF treeColor, double offset);
    void DrawDetailedTree(CDC& dc, int x, int y, int size, COLORREF leafColor, int seed);

protected:
    HICON m_hIcon;
    CBrush m_redBrush;
    CFont m_fontWarning;

    CStatic m_staticOurSpeed;
    CStatic m_staticTtcValue;
    CStatic m_staticWarning;
    CStatic m_staticDistance;
    CSliderCtrl m_sliderOurSpeed;
    CButton m_checkAcc;
    CEdit m_editTimeGap;

    CRect m_rectOurCar;
    CRect m_rectScene;

    virtual BOOL OnInitDialog();
    afx_msg void OnSysCommand(UINT nID, LPARAM lParam);
    afx_msg void OnPaint();
    afx_msg HCURSOR OnQueryDragIcon();
    afx_msg LRESULT OnShowCrashDialog(WPARAM wParam, LPARAM lParam);
    DECLARE_MESSAGE_MAP()

public:
    virtual BOOL PreTranslateMessage(MSG* pMsg);
    afx_msg void OnTimer(UINT_PTR nIDEvent);
    afx_msg void OnBnClickedStartButton();
    afx_msg HBRUSH OnCtlColor(CDC* pDC, CWnd* pWnd, UINT nCtlColor);
    afx_msg void OnBnClickedCheckAcc();
    afx_msg void OnChangeEditTimegap();
    virtual void OnOK();

    double m_dSceneryOffset_m; // 用于累积景物偏移量（单位：米）
};
