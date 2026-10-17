#include "pch.h"
#include "framework.h"
#include "ADAS.h"
#include "ADASDlg.h"
#include "afxdialogex.h"
#include <mmsystem.h>
#include "Constants.h"
#include <thread>
#pragma comment(lib, "winmm.lib")

#ifdef _DEBUG
#define new DEBUG_NEW
#endif

class CAboutDlg : public CDialogEx {
public: CAboutDlg();
#ifdef AFX_DESIGN_TIME
	  enum { IDD = IDD_ABOUTBOX };
#endif
protected: virtual void DoDataExchange(CDataExchange* pDX);
protected: DECLARE_MESSAGE_MAP()
};
CAboutDlg::CAboutDlg() : CDialogEx(IDD_ABOUTBOX) {}
void CAboutDlg::DoDataExchange(CDataExchange* pDX) { CDialogEx::DoDataExchange(pDX); }
BEGIN_MESSAGE_MAP(CAboutDlg, CDialogEx) END_MESSAGE_MAP()


	CADASDlg::CADASDlg(CWnd* pParent /*=nullptr*/)
	: CDialogEx(IDD_ADAS_DIALOG, pParent)
{
	m_hIcon = AfxGetApp()->LoadIcon(IDR_MAINFRAME);
	m_bCrashDialogShown = false;
	m_bW_KeyDown = false;
	m_bS_KeyDown = false;
	m_dwLastBeepTime = 0;
}

CADASDlg::~CADASDlg()
{
	if (m_logFile.is_open()) m_logFile.close();
}

void CADASDlg::DoDataExchange(CDataExchange* pDX)
{
	CDialogEx::DoDataExchange(pDX);
	DDX_Control(pDX, IDC_SLIDER_OUR_SPEED, m_sliderOurSpeed);
	DDX_Control(pDX, IDC_TEXT_OUR_SPEED, m_staticOurSpeed);
	DDX_Control(pDX, IDC_TTC_VALUE, m_staticTtcValue);
	DDX_Control(pDX, IDC_WARNING_TEXT, m_staticWarning);
	DDX_Control(pDX, IDC_CHECK_ACC, m_checkAcc);
	DDX_Control(pDX, IDC_EDIT_TIMEGAP, m_editTimeGap);
	DDX_Control(pDX, IDC_STATIC_DISTANCE, m_staticDistance);
}

BEGIN_MESSAGE_MAP(CADASDlg, CDialogEx)
	ON_WM_SYSCOMMAND()
	ON_WM_PAINT()
	ON_WM_QUERYDRAGICON()
	ON_WM_TIMER()
	ON_BN_CLICKED(IDC_START_BUTTON, &CADASDlg::OnBnClickedStartButton)
	ON_WM_CTLCOLOR()
	ON_MESSAGE(WM_SHOW_CRASH_DIALOG, &CADASDlg::OnShowCrashDialog)
	ON_BN_CLICKED(IDC_CHECK_ACC, &CADASDlg::OnBnClickedCheckAcc)
	ON_EN_CHANGE(IDC_EDIT_TIMEGAP, &CADASDlg::OnChangeEditTimegap)
END_MESSAGE_MAP()

BOOL CADASDlg::OnInitDialog()
{
	CDialogEx::OnInitDialog();
	ASSERT((IDM_ABOUTBOX & 0xFFF0) == IDM_ABOUTBOX);
	ASSERT(IDM_ABOUTBOX < 0xF000);
	CMenu* pSysMenu = GetSystemMenu(FALSE);
	if (pSysMenu != nullptr) {
		CString strAboutMenu;
		BOOL bNameValid;
		bNameValid = strAboutMenu.LoadString(IDS_ABOUTBOX);
		ASSERT(bNameValid);
		if (!strAboutMenu.IsEmpty()) {
			pSysMenu->AppendMenu(MF_SEPARATOR);
			pSysMenu->AppendMenu(MF_STRING, IDM_ABOUTBOX, strAboutMenu);
		}
	}
	SetIcon(m_hIcon, TRUE);
	SetIcon(m_hIcon, FALSE);

	ResetSimulation();
	m_sliderOurSpeed.SetRange(0, MAX_SPEED_KMH);
	CWnd* pWnd = GetDlgItem(IDC_SCENE_STATIC);
	if (pWnd != nullptr) pWnd->GetClientRect(&m_rectScene);
	SetTimer(1, SIM_TIMER_INTERVAL_MS, nullptr);
	m_redBrush.CreateSolidBrush(RGB(255, 0, 0));
	m_fontWarning.CreateFont(24, 0, 0, 0, FW_BOLD, FALSE, FALSE, 0, DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS, DEFAULT_QUALITY, DEFAULT_PITCH | FF_SWISS, _T("黑体"));
	m_staticWarning.SetFont(&m_fontWarning);
	m_editTimeGap.SetWindowText(_T("2.0"));
	GetDlgItem(IDC_START_BUTTON)->SetFocus();
	return FALSE;
}

void CADASDlg::OnSysCommand(UINT nID, LPARAM lParam)
{
	if ((nID & 0xFFF0) == IDM_ABOUTBOX)
	{
		CAboutDlg dlgAbout;
		dlgAbout.DoModal();
	}
	else
	{
		CDialogEx::OnSysCommand(nID, lParam);
	}
}

void CADASDlg::OnPaint()
{
	if (IsIconic())
	{
		CPaintDC dc(this);
		SendMessage(WM_ICONERASEBKGND, reinterpret_cast<WPARAM>(dc.GetSafeHdc()), 0);
		int cxIcon = GetSystemMetrics(SM_CXICON);
		int cyIcon = GetSystemMetrics(SM_CYICON);
		CRect rect;
		GetClientRect(&rect);
		int x = (rect.Width() - cxIcon + 1) / 2;
		int y = (rect.Height() - cyIcon + 1) / 2;
		dc.DrawIcon(x, y, m_hIcon);
	}
	else
	{
		CDialogEx::OnPaint();
		CWnd* pWnd = GetDlgItem(IDC_SCENE_STATIC);
		if (pWnd == NULL) return;
		CDC* pDC = pWnd->GetDC();
		if (pDC == NULL) return;

		// 使用双缓冲防止闪烁
		CDC memDC;
		CBitmap memBitmap;
		memDC.CreateCompatibleDC(pDC);
		memBitmap.CreateCompatibleBitmap(pDC, m_rectScene.Width(), m_rectScene.Height());
		memDC.SelectObject(&memBitmap);

		// ---  绘制动态背景
		DrawRoadSideScenery(memDC);

		// ---  绘制道路和车道线的逻辑
		int roadWidth = LANE_COUNT * LANE_WIDTH_PX;
		int roadStartX = (m_rectScene.Width() - roadWidth) / 2;
		int roadCenterX = roadStartX + roadWidth / 2;
		CRect roadRect(roadStartX, 0, roadStartX + roadWidth, m_rectScene.Height());
		memDC.FillSolidRect(roadRect, RGB(100, 100, 100));
		CPen whitePen(PS_DASH, 1, RGB(255, 255, 255));
		CPen* pOldPen = memDC.SelectObject(&whitePen);
		for (int i = 1; i < LANE_COUNT; ++i) {
			int lineX = roadStartX + i * LANE_WIDTH_PX;
			memDC.MoveTo(lineX, 0);
			memDC.LineTo(lineX, m_rectScene.Height());
		}
		memDC.SelectObject(pOldPen);

		// 引擎逻辑：根据精确的横向偏移绘制我车
		int carWidth = CAR_WIDTH_PX;
		int carHeight = CAR_HEIGHT_PX;
		int ourCarX = roadCenterX + static_cast<int>(m_engine.GetOurCarLateralPos_px()) - carWidth / 2;
		int ourCarY = m_rectScene.Height() * 3 / 4;
		m_rectOurCar.SetRect(ourCarX, ourCarY, ourCarX + carWidth, ourCarY + carHeight);
		DrawAnimeStyleCar(memDC, ourCarX, ourCarY, carWidth, carHeight, RGB(0, 100, 255), true);


		// 引擎逻辑：绘制交通车辆并根据TTC变色
		const std::vector<VehicleState>& traffic = m_engine.GetTrafficVehicles();
		CRect primaryTargetRect;
		for (const auto& vehicle : traffic) {
			int vehicleX = roadCenterX + static_cast<int>(vehicle.lateralPosition_px) - carWidth / 2;
			int dist_pixel = static_cast<int>(vehicle.position_y_m * PIXELS_PER_METER);
			int vehicleY = ourCarY - carHeight - dist_pixel;

			COLORREF carColor = RGB(150, 150, 150); // 默认颜色
			if (vehicle.id == m_engine.GetPrimaryTargetId()) {
				primaryTargetRect.SetRect(vehicleX, vehicleY, vehicleX + carWidth, vehicleY + carHeight);
				// 您的TTC变色逻辑
				if (m_engine.GetTTC() < TTC_WARNING && m_engine.GetTTC() > 0 && !m_engine.HasCrashed()) {
					carColor = RGB(255, 0, 0); // 危险时变红
				}
			}
			DrawAnimeStyleCar(memDC, vehicleX, vehicleY, carWidth, carHeight, carColor, false);
		}

		// 撞击效果逻辑
		if (m_engine.HasCrashed() && m_engine.GetPrimaryTargetId() != -1) {
			CPoint impactPoint = primaryTargetRect.TopLeft();
			impactPoint.x += carWidth / 2;
			CPen explosionPen(PS_SOLID, 3, RGB(255, 69, 0));
			CPen* pOldPenExp = memDC.SelectObject(&explosionPen);
			for (int i = 0; i < 12; ++i) {
				double angle = i * 30.0 * 3.14159 / 180.0;
				int x1 = impactPoint.x + static_cast<int>(cos(angle) * 10);
				int y1 = impactPoint.y + static_cast<int>(sin(angle) * 10);
				int x2 = impactPoint.x + static_cast<int>(cos(angle) * 40);
				int y2 = impactPoint.y + static_cast<int>(sin(angle) * 40);
				memDC.MoveTo(x1, y1);
				memDC.LineTo(x2, y2);
			}
			memDC.SelectObject(pOldPenExp);
		}

		//将内存DC的内容一次性绘制到屏幕上
		pDC->BitBlt(0, 0, m_rectScene.Width(), m_rectScene.Height(), &memDC, 0, 0, SRCCOPY);
		pWnd->ReleaseDC(pDC);
	}
}
HCURSOR CADASDlg::OnQueryDragIcon()
{
	return static_cast<HCURSOR>(m_hIcon);
}
// ADASDlg.cpp
void CADASDlg::UpdateUIFromEngine()
{
	// --- 从引擎获取所有最新状态 ---
	double ttc = m_engine.GetTTC();
	bool hasCrashed = m_engine.HasCrashed();
	int ourSpeed_kmh = static_cast<int>(m_engine.GetOurSpeed_ms() * 3.6);
	double distance = m_engine.GetDistance();
	CSimulationEngine::LaneChangeAdvice advice = m_engine.GetLaneChangeAdvice();
	bool isRearWarning = m_engine.IsRearCollisionWarningActive();

	//  决策预警文本
	CString warningText = _T("状态正常");
	if (hasCrashed) {
		warningText = _T("!!! 车辆已撞毁 !!!");
	}
	else if (advice != CSimulationEngine::Safe) {
		if (advice == CSimulationEngine::Unsafe_RearTooClose) warningText = _T("空间不足，禁止变道！");
		else warningText = _T("空间不足，禁止变道！");
	}
	else if (ttc < TTC_WARNING && ttc > 0) {
		warningText = _T("!!! 前方危险, 请减速 !!!");
	}
	else if (isRearWarning) {
		warningText = _T("!!! 后方危险, 谨防追尾 !!!");
	}
	m_staticWarning.SetWindowText(warningText);
	bool shouldPlayWarning = !hasCrashed && ((ttc < TTC_WARNING && ttc > 0) || isRearWarning);
	if (shouldPlayWarning)
	{
		DWORD currentTime_ms = GetTickCount();
		if (currentTime_ms - m_dwLastBeepTime > 150)
		{
			m_dwLastBeepTime = currentTime_ms;
			MessageBeep(0);
		}

	}

	// --- 3. 更新其他UI控件 ---
	CString str;
	str.Format(_T("TTC (秒): %.2f"), ttc);
	m_staticTtcValue.SetWindowText(str);
	str.Format(_T("当前距离(m): %.2f"), distance);
	m_staticDistance.SetWindowText(str);
	m_sliderOurSpeed.SetPos(ourSpeed_kmh);
	str.Format(_T("主车速度: %d km/h"), ourSpeed_kmh);
	m_staticOurSpeed.SetWindowText(str);

	// --- 4. 通知场景重绘 ---
	CRect rc;
	GetDlgItem(IDC_SCENE_STATIC)->GetWindowRect(&rc);
	ScreenToClient(&rc);
	InvalidateRect(&rc, FALSE);
}

void CADASDlg::OnTimer(UINT_PTR nIDEvent)
{
	if (nIDEvent == 1)
	{
		double current_acceleration = 0.0;
		if (m_engine.IsRunning())
		{
			if (m_engine.IsAccOn())
			{
				bool isRearWarning = m_engine.IsRearCollisionWarningActive();
				bool evasiveLaneChangeExecuted = false;

				if (isRearWarning)
				{
					// 创建一个代表玩家当前状态的临时对象
					VehicleState tempPlayerState;
					tempPlayerState.id = 0; // 玩家ID设为0
					tempPlayerState.position_y_m = 0;
					tempPlayerState.speed_ms = m_engine.GetOurSpeed_ms();
					tempPlayerState.lateralPosition_px = m_engine.GetOurCarLateralPos_px();
					tempPlayerState.targetLaneIndex = m_engine.GetOurCarLane();

					int currentLane = m_engine.GetOurCarLane();
					int escapeLanes[] = { currentLane - 1, currentLane + 1 }; // 尝试左右

					for (int targetLane : escapeLanes)
					{
						if (targetLane < 0 || targetLane >= LANE_COUNT) continue;

						if (m_engine.IsLaneChangeSafe(tempPlayerState, targetLane))
						{
							m_engine.ExecuteAutomatedLaneChange(targetLane);
							evasiveLaneChangeExecuted = true;
							break;
						}
					}
				}
				// 如果未执行自动变道（包括后方没有危险的正常情况），则运行常规的防御性ACC
				if (!evasiveLaneChangeExecuted)
				{
					double effectiveTimeGap = m_engine.GetDesiredTimeGap();
					if (isRearWarning)
					{
						const double MIN_SAFE_TIME_GAP = 0.8;
						effectiveTimeGap = MIN_SAFE_TIME_GAP;
					}

					double ourSpeed = m_engine.GetOurSpeed_ms();
					double actualDistance = m_engine.GetDistance();
					double desiredDistance = effectiveTimeGap * ourSpeed;
					double error = actualDistance - desiredDistance;
					current_acceleration = ACC_PROPORTIONAL_GAIN * error;

					if (current_acceleration > MAX_ACCELERATION_MS2) current_acceleration = MAX_ACCELERATION_MS2;
					else if (current_acceleration < -MAX_DECELERATION_MS2) current_acceleration = -MAX_DECELERATION_MS2;
				}
				else
				{
					// 如果执行了自动变道，则本帧不再控制加减速，让车辆平稳完成变道
					current_acceleration = 0.0;
				}
			}
			else
			{
				if (m_bW_KeyDown) current_acceleration = MAX_ACCELERATION_MS2;
				else if (m_bS_KeyDown) current_acceleration = -MAX_DECELERATION_MS2;
			}
			m_engine.Update(SIM_TIME_STEP_S, current_acceleration, m_rectScene);
			m_dSceneryOffset_m += m_engine.GetOurSpeed_ms() * SIM_TIME_STEP_S;
		}
		UpdateUIFromEngine();
		if (m_engine.HasCrashed() && !m_bCrashDialogShown)
		{
			m_bCrashDialogShown = true;
			PlaySound(MAKEINTRESOURCE(IDR_WAVE_CRASH), AfxGetInstanceHandle(), SND_RESOURCE | SND_ASYNC);
			PostMessage(WM_SHOW_CRASH_DIALOG);
		}
	}
	CDialogEx::OnTimer(nIDEvent);
}

void CADASDlg::OnBnClickedStartButton()
{
	if (m_engine.IsRunning())
	{
		m_engine.SetRunning(false);
		GetDlgItem(IDC_START_BUTTON)->SetWindowText(_T("继续仿真"));
		if (m_logFile.is_open()) m_logFile.close();
	}
	else
	{
		if (m_engine.GetScenarioTime() == 0.0)
		{
			m_logFile.open("adas_log.csv", std::ios::out | std::ios::trunc);
			if (m_logFile.is_open())
			{
				m_logFile << "Timestamp(s),OurSpeed(km/h),PrimaryTargetSpeed(km/h),Distance(m),TTC(s),ACC_Status,Acceleration(m/s^2)" << std::endl;
			}
		}
		m_engine.SetRunning(true);
		GetDlgItem(IDC_START_BUTTON)->SetWindowText(_T("停止仿真"));
	}
}

BOOL CADASDlg::PreTranslateMessage(MSG* pMsg)
{
	if (pMsg->message == WM_KEYDOWN)
	{
		if (pMsg->wParam == 'W') { m_bW_KeyDown = true; return TRUE; }
		if (pMsg->wParam == 'S') { m_bS_KeyDown = true; return TRUE; }
		if (pMsg->wParam == VK_SPACE) { OnBnClickedStartButton(); return TRUE; }
		if (pMsg->wParam == 'C') { m_checkAcc.SetCheck(!m_checkAcc.GetCheck()); OnBnClickedCheckAcc(); return TRUE; }
		if (pMsg->wParam == 'A')
		{
			m_engine.ChangeLaneLeft();
			return TRUE;
		}
		if (pMsg->wParam == 'D')
		{
			m_engine.ChangeLaneRight();
			return TRUE;
		}
	}
	else if (pMsg->message == WM_KEYUP)
	{
		if (pMsg->wParam == 'W') { m_bW_KeyDown = false; return TRUE; }
		if (pMsg->wParam == 'S') { m_bS_KeyDown = false; return TRUE; }
	}
	return CDialogEx::PreTranslateMessage(pMsg);
}

HBRUSH CADASDlg::OnCtlColor(CDC* pDC, CWnd* pWnd, UINT nCtlColor)
{
	HBRUSH hbr = CDialogEx::OnCtlColor(pDC, pWnd, nCtlColor);
	if (pWnd->GetDlgCtrlID() == IDC_WARNING_TEXT)
	{
		// 从引擎获取所有相关的状态
		bool isFCWarning = (m_engine.GetTTC() < TTC_WARNING && m_engine.GetTTC() > 0);
		bool hasCrashed = m_engine.HasCrashed();
		bool isRearWarning = m_engine.IsRearCollisionWarningActive();
		CSimulationEngine::LaneChangeAdvice advice = m_engine.GetLaneChangeAdvice();
		bool isLaneChangeUnsafe = (advice != CSimulationEngine::Safe);

		// 只要满足任意一个危险或警告条件，就把背景变红
		if (isFCWarning || hasCrashed || isRearWarning || isLaneChangeUnsafe)
		{
			pDC->SetTextColor(RGB(255, 255, 255)); // 白色文字
			pDC->SetBkMode(TRANSPARENT);
			return m_redBrush; // 红色背景
		}
	}
	return hbr;
}
void CADASDlg::ResetSimulation()
{
	m_engine.Reset();
	m_bCrashDialogShown = false;
	m_dwLastBeepTime = 0;
	UpdateUIFromEngine();
	m_dSceneryOffset_m = 0.0;
	GetDlgItem(IDC_START_BUTTON)->EnableWindow(TRUE);
	GetDlgItem(IDC_START_BUTTON)->SetWindowText(_T("开始仿真"));
}

LRESULT CADASDlg::OnShowCrashDialog(WPARAM wParam, LPARAM lParam)
{
	if (AfxMessageBox(_T("车辆已撞毁！\n\n是否要重新开始仿真？"), MB_YESNO | MB_ICONWARNING) == IDYES)
	{
		ResetSimulation();
	}
	else
	{
		PostQuitMessage(0);
	}
	return 0;
}

void CADASDlg::OnBnClickedCheckAcc()
{
	bool isChecked = (m_checkAcc.GetCheck() == BST_CHECKED);
	m_engine.SetAccStatus(isChecked);
	if (isChecked)
	{
		OnChangeEditTimegap();
	}
}

void CADASDlg::OnChangeEditTimegap()
{
	if (m_engine.IsAccOn())
	{
		CString strTimeGap;
		m_editTimeGap.GetWindowText(strTimeGap);
		if (!strTimeGap.IsEmpty())
		{
			double timeGap = _tstof(strTimeGap);
			m_engine.SetDesiredTimeGap(timeGap);
		}
	}
}

void CADASDlg::OnOK() {}


void CADASDlg::DrawAnimeStyleCar(CDC& dc, int x, int y, int width, int height, COLORREF carColor, bool isOurCar)
{
	// 车身主体 - 使用圆角矩形
	CBrush carBrush(carColor);
	CPen carPen(PS_SOLID, 2, RGB(max(0, GetRValue(carColor) - 50), max(0, GetGValue(carColor) - 50), max(0, GetBValue(carColor) - 50)));
	dc.SelectObject(&carBrush);
	dc.SelectObject(&carPen);
	dc.RoundRect(x, y, x + width, y + height, width / 3, height / 4);

	// 车窗 - 浅蓝色，略小于车身
	CBrush windowBrush(RGB(180, 220, 255));
	dc.SelectObject(&windowBrush);
	dc.RoundRect(x + width / 6, y + height / 4, x + width * 5 / 6, y + height * 3 / 4, width / 6, height / 8);

	// 车头（上方）的小轮胎
	CBrush mirrorBrush(RGB(80, 80, 80));
	dc.SelectObject(&mirrorBrush);
	// 左轮胎
	dc.Ellipse(x - width / 10, y + height / 6, x + width / 10, y + height / 3);
	// 右轮胎
	dc.Ellipse(x + width - width / 10, y + height / 6, x + width + width / 10, y + height / 3);

	// 车尾（下方）的轮胎
	CBrush rearTireBrush(RGB(80, 80, 80));
	dc.SelectObject(&rearTireBrush);
	// 左后轮胎
	dc.Ellipse(x - width / 10, y + height * 2 / 3, x + width / 10, y + height * 5 / 6);
	// 右后轮胎
	dc.Ellipse(x + width - width / 10, y + height * 2 / 3, x + width + width / 10, y + height * 5 / 6);

	// 车尾灯（下方）- 红色小椭圆
	CBrush taillightBrush(RGB(255, 80, 80));
	dc.SelectObject(&taillightBrush);
	// 左尾灯
	dc.Ellipse(x + width / 6, y + height - height / 8, x + width / 3, y + height);
	// 右尾灯
	dc.Ellipse(x + width * 2 / 3, y + height - height / 8, x + width * 5 / 6, y + height);

	// 车头灯（上方）- 黄色小椭圆
	CBrush headlightBrush(RGB(255, 255, 150));
	dc.SelectObject(&headlightBrush);
	// 左前灯
	dc.Ellipse(x + width / 6, y, x + width / 3, y + height / 8);
	// 右前灯
	dc.Ellipse(x + width * 2 / 3, y, x + width * 5 / 6, y + height / 8);

	// 车窗反光效果 - 白色细线
	CPen reflectPen(PS_SOLID, 1, RGB(255, 255, 255));
	dc.SelectObject(&reflectPen);
	dc.MoveTo(x + width / 4, y + height / 3);
	dc.LineTo(x + width * 3 / 4, y + height / 2);

	// 如果是主车，添加特殊标识
	if (isOurCar) {
		CBrush ourCarBrush(RGB(255, 255, 0));
		dc.SelectObject(&ourCarBrush);
		dc.Ellipse(x + width / 2 - width / 12, y + height / 2 - width / 12,
			x + width / 2 + width / 12, y + height / 2 + width / 12);
	}
}

void CADASDlg::DrawRoadSideScenery(CDC& dc)
{
	double ourSpeed_ms = m_engine.GetOurSpeed_ms();
	double scenarioTime = m_engine.GetScenarioTime();

	int roadWidth = LANE_COUNT * LANE_WIDTH_PX;
	int roadStartX = (m_rectScene.Width() - roadWidth) / 2;
	int roadEndX = roadStartX + roadWidth;

	COLORREF skyColor = RGB(135, 206, 235);
	COLORREF buildingColor = RGB(120, 120, 120);
	COLORREF grassColor = RGB(34, 139, 34);
	COLORREF treeColor = RGB(0, 100, 0); // A darker, more natural green

	CRect skyRect(0, 0, m_rectScene.Width(), m_rectScene.Height() / 2);
	CBrush skyBrush(skyColor);
	dc.FillRect(&skyRect, &skyBrush);

	DrawMovingClouds(dc, skyRect, ourSpeed_ms, scenarioTime);


	DrawDistantBuildings(dc, buildingColor); // 2. 在森林之上绘制建筑

	CRect groundRect(0, m_rectScene.Height() / 2, m_rectScene.Width(), m_rectScene.Height());
	CBrush grassBrush(grassColor);
	dc.FillRect(&groundRect, &grassBrush);

	double treeOffsetInPixels = m_dSceneryOffset_m * PIXELS_PER_METER;

	DrawDynamicTreeRows(dc, 0, roadStartX - 30, treeColor, treeOffsetInPixels);
	DrawDynamicTreeRows(dc, roadEndX + 30, m_rectScene.Width(), treeColor, treeOffsetInPixels);
}
void CADASDlg::DrawDynamicTreeRows(CDC& dc, int startX, int endX, COLORREF treeColor, double offset)
{
	int treeSpacing = 50;
	int treeSize = 30;
	int groundLevel = m_rectScene.Height() / 2;
	int sceneHeight = m_rectScene.Height() - groundLevel;
	int offsetPixels = static_cast<int>(offset) % sceneHeight;

	if (sceneHeight <= 0) return; // 防止除零错误

	for (int x = startX + 25; x < endX - 25; x += treeSpacing) {
		for (int row = 0; row < 4; row++) {
			int baseTreeY = groundLevel + 50 + row * 60;
			int treeY = baseTreeY + offsetPixels;
			if (treeY > m_rectScene.Height() + treeSize) {
				treeY -= sceneHeight;
			}
			if (treeY > groundLevel - treeSize && treeY < m_rectScene.Height() + treeSize) {
				int seed = (x / treeSpacing) * 100 + row * 10;
				DrawDetailedTree(dc, x, treeY, treeSize, treeColor, seed);
			}
			int extraTreeY = treeY + sceneHeight; // 修正循环逻辑
			if (extraTreeY > groundLevel - treeSize && extraTreeY < m_rectScene.Height() + treeSize) {
				int extraSeed = (x / treeSpacing) * 100 + row * 10 + 1000;
				DrawDetailedTree(dc, x, extraTreeY, treeSize, treeColor, extraSeed);
			}
		}
	}
}

void CADASDlg::DrawMovingClouds(CDC& dc, const CRect& skyRect, double ourSpeed_ms, double scenarioTime)
{
	COLORREF cloudColor = RGB(255, 255, 255);
	int cloudWidth = 100;
	int cloudHeight = 50;
	int cloudCount = 5;
	// 修正 fmod 对负数的处理，并确保循环范围正确
	double totalWidth = skyRect.Width() * 1.5;
	double cloudOffset = fmod(scenarioTime * 5.0 + ourSpeed_ms * 0.2, totalWidth);


	CBrush cloudBrush(cloudColor);
	dc.SelectObject(&cloudBrush);
	dc.SelectObject(GetStockObject(NULL_PEN));

	for (int i = 0; i < cloudCount; ++i) {
		int baseX = static_cast<int>(i * 250 - cloudOffset);
		int baseY = skyRect.top + (i % 2 == 0 ? 50 : 100);

		// 循环逻辑: 当一个云朵完全移出左边，将它重新放置到右边
		if (baseX + cloudWidth < 0) {
			baseX += static_cast<int>(totalWidth);
		}

		dc.Ellipse(baseX, baseY, baseX + cloudWidth, baseY + cloudHeight);
	}
}

void CADASDlg::DrawDetailedTree(CDC& dc, int x, int y, int size, COLORREF leafColor, int seed)
{
	// 边界检查
	if (x < -size || x >= m_rectScene.Width() + size || y < -size || y >= m_rectScene.Height() + size) return;

	// 树干 - 简化版本
	CBrush trunkBrush(RGB(101, 67, 33));
	dc.SelectObject(&trunkBrush);

	// 主树干
	int trunkWidth = size / 6;
	int trunkHeight = size / 2;
	dc.Rectangle(x - trunkWidth / 2, y - trunkHeight, x + trunkWidth / 2, y);

	// 树冠 - 简单的圆形
	CBrush leafBrush(leafColor);
	dc.SelectObject(&leafBrush);

	// 主树冠
	int crownRadius = size / 2;
	dc.Ellipse(x - crownRadius, y - trunkHeight - crownRadius,
		x + crownRadius, y - trunkHeight + crownRadius / 2);

	// 添加树冠层次感 - 稍小的内层
	COLORREF darkerLeaf = RGB(
		max(0, GetRValue(leafColor) - 20),
		max(0, GetGValue(leafColor) - 20),
		max(0, GetBValue(leafColor) - 20)
	);
	CBrush darkLeafBrush(darkerLeaf);
	dc.SelectObject(&darkLeafBrush);

	int innerRadius = crownRadius * 2 / 3;
	dc.Ellipse(x - innerRadius, y - trunkHeight - innerRadius,
		x + innerRadius, y - trunkHeight + innerRadius / 3);
}

void CADASDlg::DrawDistantBuildings(CDC& dc, COLORREF baseColor)
{
	// 绘制固定的远景建筑轮廓
	int buildingCount = m_rectScene.Width() / 50; // 建筑数量

	for (int i = 0; i < buildingCount; i++) {
		int buildingX = i * 50 + (i * 3) % 10; // 固定位置
		int buildingHeight = 25 + (i * 5) % 60; // 固定高度
		int buildingWidth = 40 + (i * 2) % 25;  // 固定宽度

		// 建筑颜色固定变化
		int colorVariation = (i * 10) % 30 - 15;
		COLORREF buildingColor = RGB(
			max(0, min(255, GetRValue(baseColor) + colorVariation)),
			max(0, min(255, GetGValue(baseColor) + colorVariation)),
			max(0, min(255, GetBValue(baseColor) + colorVariation))
		);

		CBrush buildingBrush(buildingColor);
		dc.SelectObject(&buildingBrush);
		dc.Rectangle(buildingX, m_rectScene.Height() / 2 - buildingHeight,
			buildingX + buildingWidth, m_rectScene.Height() / 2);

		// 绘制固定的建筑窗户
		CBrush windowBrush(RGB(255, 255, 200));
		dc.SelectObject(&windowBrush);
		for (int wx = 0; wx < buildingWidth / 10; wx++) {
			for (int wy = 0; wy < buildingHeight / 8; wy++) {
				if ((wx + wy + i) % 3 != 0) { // 固定的窗户模式
					int windowX = buildingX + 3 + wx * 10;
					int windowY = m_rectScene.Height() / 2 - buildingHeight + 3 + wy * 8;
					dc.Rectangle(windowX, windowY, windowX + 5, windowY + 4);
				}
			}
		}

		// 固定的建筑顶部装饰
		if (i % 3 == 0) {
			CBrush roofBrush(RGB(
				min(255, GetRValue(buildingColor) + 15),
				min(255, GetGValue(buildingColor) + 15),
				min(255, GetBValue(buildingColor) + 15)
			));
			dc.SelectObject(&roofBrush);
			dc.Rectangle(buildingX - 1, m_rectScene.Height() / 2 - buildingHeight - 3,
				buildingX + buildingWidth + 1, m_rectScene.Height() / 2 - buildingHeight);
		}
	}
}
