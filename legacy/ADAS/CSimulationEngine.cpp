#include "pch.h"
#include "CSimulationEngine.h"
#include "Constants.h"

CSimulationEngine::CSimulationEngine()
{
	std::random_device rd;
	m_rng.seed(rd());
	Reset();
}

void CSimulationEngine::Reset()
{
	m_bIsRunning = false;
	m_bHasCrashed = false;
	m_dOurSpeed_ms = INITIAL_OUR_SPEED_KMH / 3.6;
	m_nOurCarLane = 1;
	m_dOurCarLateralPos_px = 0.0;       // 中间车道横向偏移为0
	m_dOurCarTargetLateralPos_px = 0.0; // 目标也是中间车道
	m_dScenarioTime = 0.0;
	m_bAccOn = false;
	m_dDesiredTimeGap_s = 2.0;
	m_trafficVehicles.clear();
	m_nPrimaryTargetId = -1;

	std::uniform_real_distribution<double> time_dist(5.0, 15.0);
	m_dCutInTriggerTime_s = time_dist(m_rng);

	std::uniform_int_distribution<int> lane_dist(0, 1);
	int startLane = (lane_dist(m_rng) == 0) ? 0 : 2;

	m_laneChangeAdvice = LaneChangeAdvice::Safe;
	m_laneChangeAdviceTimestamp = 0.0;
	m_bRearCollisionWarning = false;

	VehicleState frontCar;
	frontCar.id = 1;
	frontCar.position_y_m = INITIAL_DISTANCE_M;
	frontCar.speed_ms = INITIAL_FRONT_SPEED_KMH / 3.6;
	frontCar.targetLaneIndex = 1;
	frontCar.lateralPosition_px = 0.0;
	frontCar.isCutInCar = false;
	frontCar.state = VehicleState::Following;
	frontCar.nextState = VehicleState::Following;
	m_trafficVehicles.push_back(frontCar);

	VehicleState cutInCar;
	cutInCar.id = 2;
	cutInCar.position_y_m = -40.0;
	cutInCar.speed_ms = (INITIAL_OUR_SPEED_KMH + 30) / 3.6;
	cutInCar.targetLaneIndex = startLane;
	cutInCar.originalLaneIndex = startLane;
	cutInCar.lateralPosition_px = (startLane == 0) ? -LANE_WIDTH_PX : LANE_WIDTH_PX;
	cutInCar.isCutInCar = true;
	cutInCar.state = VehicleState::Following;
	cutInCar.nextState = VehicleState::Following;
	cutInCar.cooldownEndTime_s = 0.0;
	m_trafficVehicles.push_back(cutInCar);

	m_nNextVehicleId = 3; // ID 1和2已经被占用了
	m_dNextSpawnTime_s = 2.0; // 仿真开始2秒后，生成第一波新车

	m_dTTC = 999.0;
}

void CSimulationEngine::Update(double timeStep, double acceleration_ms2, const CRect& rectScene)
{
	if (!m_bIsRunning || m_bHasCrashed) return;

	//调用生成逻辑
	if (m_dScenarioTime > m_dNextSpawnTime_s)
	{
		SpawnVehicle();
		// 随机决定下一次生成的时间
		std::uniform_real_distribution<double> interval_dist(2.0, 5.0);
		m_dNextSpawnTime_s = m_dScenarioTime + interval_dist(m_rng);
	}

	if (m_laneChangeAdvice != LaneChangeAdvice::Safe && (m_dScenarioTime > m_laneChangeAdviceTimestamp + 1.5))
	{
		m_laneChangeAdvice = LaneChangeAdvice::Safe;
	}

	// 更新我车横向位置
	double lateral_diff = m_dOurCarTargetLateralPos_px - m_dOurCarLateralPos_px;
	if (abs(lateral_diff) > 1.0)
	{
		double move_distance = LANE_CHANGE_SPEED_PX_PER_S * timeStep;
		if (lateral_diff > 0) {
			m_dOurCarLateralPos_px += (std::min)(move_distance, lateral_diff);
		}
		else {
			m_dOurCarLateralPos_px -= (std::min)(move_distance, -lateral_diff);
		}
	}
	else {
		m_dOurCarLateralPos_px = m_dOurCarTargetLateralPos_px;
	}

	m_dScenarioTime += timeStep;

	// 更新我车速度
	m_dOurSpeed_ms += acceleration_ms2 * timeStep;
	if (m_dOurSpeed_ms < 0) m_dOurSpeed_ms = 0;
	if (m_dOurSpeed_ms > (MAX_SPEED_KMH / 3.6)) m_dOurSpeed_ms = (MAX_SPEED_KMH / 3.6);

	// --- 阶段一：决策 ---
	for (auto& vehicle : m_trafficVehicles)
	{
		vehicle.nextState = vehicle.state;
		vehicle.nextTargetLaneIndex = vehicle.targetLaneIndex;

		switch (vehicle.state)
		{
		case VehicleState::Following:
		{
			if (vehicle.id == 1)
			{
				double base_speed_ms = INITIAL_FRONT_SPEED_KMH / 3.6;
				double speed_variation_ms = 10.0 / 3.6;
				vehicle.speed_ms = base_speed_ms + speed_variation_ms * sin(m_dScenarioTime * 0.5);
			}
			else if (vehicle.id == 2 && m_dScenarioTime > m_dCutInTriggerTime_s && m_dScenarioTime > vehicle.cooldownEndTime_s)
			{
				vehicle.nextState = VehicleState::PreparingToCutIn;
			}
			else if (vehicle.id > 2 && m_dScenarioTime > vehicle.nextLaneChangeCheckTime_s)
			{
				int dir = (m_rng() % 2 == 0) ? -1 : 1;
				int potentialTargetLane = vehicle.targetLaneIndex + dir;
				if (potentialTargetLane >= 0 && potentialTargetLane < LANE_COUNT)
				{
					if (IsLaneChangeSafe(vehicle, potentialTargetLane))
					{
						vehicle.nextState = VehicleState::ChangingLane;
						vehicle.nextTargetLaneIndex = potentialTargetLane;
					}
				}
				std::uniform_real_distribution<double> change_time_dist(8.0, 20.0);
				vehicle.nextLaneChangeCheckTime_s = m_dScenarioTime + change_time_dist(m_rng);
			}
			break;
		}
		case VehicleState::PreparingToCutIn:
		{
			if (vehicle.position_y_m > -5.0 && IsLaneChangeSafe(vehicle, 1))
			{
				vehicle.nextState = VehicleState::CuttingIn;
			}
			break;
		}
		case VehicleState::CuttingIn:
		{
			double targetLateralPos = 0.0;
			if (abs(vehicle.lateralPosition_px - targetLateralPos) < 1.0)
			{
				vehicle.nextState = VehicleState::Braking;
				vehicle.stateChangeTimestamp = m_dScenarioTime;
			}
			break;
		}
		case VehicleState::Braking:
		{
			if (vehicle.speed_ms <= (INITIAL_FRONT_SPEED_KMH - 10) / 3.6)
			{
				vehicle.nextState = VehicleState::Stabilizing;
				vehicle.stateChangeTimestamp = m_dScenarioTime;
			}
			break;
		}
		case VehicleState::Stabilizing:
		{
			if (m_dScenarioTime - vehicle.stateChangeTimestamp > 3.0)
			{
				vehicle.nextState = VehicleState::ReturningToLane;
			}
			break;
		}
		case VehicleState::ReturningToLane:
		{
			double targetLateralPos = (vehicle.originalLaneIndex == 0) ? -LANE_WIDTH_PX : LANE_WIDTH_PX;
			if (abs(vehicle.lateralPosition_px - targetLateralPos) < 1.0)
			{
				vehicle.nextState = VehicleState::Following;
				vehicle.nextTargetLaneIndex = vehicle.originalLaneIndex;
				std::uniform_real_distribution<double> cooldown_dist(10.0, 25.0);
				vehicle.cooldownEndTime_s = m_dScenarioTime + cooldown_dist(m_rng);
			}
			break;
		}
		case VehicleState::ChangingLane:
		{
			double targetLateralPos = (vehicle.targetLaneIndex - 1) * LANE_WIDTH_PX;
			if (abs(vehicle.lateralPosition_px - targetLateralPos) < 1.0)
			{
				vehicle.nextState = VehicleState::Following;
			}
			break;
		}
		}
	}

	// --- 阶段二：冲突解决 ---
	for (auto& vehicleA : m_trafficVehicles)
	{
		if (vehicleA.nextState != VehicleState::ChangingLane) continue;
		for (auto& vehicleB : m_trafficVehicles)
		{
			if (vehicleA.id == vehicleB.id) continue;
			if (vehicleB.nextState == VehicleState::ChangingLane && vehicleA.nextTargetLaneIndex == vehicleB.nextTargetLaneIndex)
			{
				if (vehicleA.position_y_m < vehicleB.position_y_m) {
					vehicleA.nextState = VehicleState::Following;
				}
				else {
					vehicleB.nextState = VehicleState::Following;
				}
			}
		}
	}

	// --- 阶段三：行动 ---
	for (auto& vehicle : m_trafficVehicles)
	{
		vehicle.state = vehicle.nextState;
		vehicle.targetLaneIndex = vehicle.nextTargetLaneIndex;

		if (vehicle.state == VehicleState::Braking)
		{
			vehicle.speed_ms -= BRAKE_CHECK_DECELERATION_MS2 * timeStep;
			if (vehicle.speed_ms < 0) vehicle.speed_ms = 0;
		}

		switch (vehicle.state)
		{
		case VehicleState::CuttingIn:
		case VehicleState::ReturningToLane:
		case VehicleState::ChangingLane:
		{
			double targetLateralPos = (vehicle.state == VehicleState::CuttingIn) ? 0.0 : (vehicle.targetLaneIndex - 1) * LANE_WIDTH_PX;
			if (vehicle.originalLaneIndex != -1 && vehicle.state == VehicleState::ReturningToLane) {
				targetLateralPos = (vehicle.originalLaneIndex - 1) * LANE_WIDTH_PX;
			}

			double lateral_diff_ai = targetLateralPos - vehicle.lateralPosition_px;
			if (abs(lateral_diff_ai) > 1.0) {
				double move_distance = LANE_CHANGE_SPEED_PX_PER_S * timeStep;
				if (lateral_diff_ai > 0) {
					vehicle.lateralPosition_px += (std::min)(move_distance, lateral_diff_ai);
				}
				else {
					vehicle.lateralPosition_px -= (std::min)(move_distance, -lateral_diff_ai);
				}
			}
			else {
				vehicle.lateralPosition_px = targetLateralPos;
			}
			break;
		}
		}

		double relative_speed_ms = m_dOurSpeed_ms - vehicle.speed_ms;
		vehicle.position_y_m -= relative_speed_ms * timeStep;
	}

	// 碰撞检测
	int roadWidth = LANE_COUNT * LANE_WIDTH_PX;
	int roadStartX = (rectScene.Width() - roadWidth) / 2;
	int roadCenterX = roadStartX + roadWidth / 2;
	int ourCarX_logic = roadCenterX + static_cast<int>(m_dOurCarLateralPos_px) - CAR_WIDTH_PX / 2;
	int ourCarY_logic = rectScene.Height() * 3 / 4;
	CRect rectOurCar(ourCarX_logic, ourCarY_logic, ourCarX_logic + CAR_WIDTH_PX, ourCarY_logic + CAR_HEIGHT_PX);

	for (const auto& vehicle : m_trafficVehicles)
	{
		int vehicleX_logic = roadCenterX + static_cast<int>(vehicle.lateralPosition_px) - CAR_WIDTH_PX / 2;
		int dist_pixel = static_cast<int>(vehicle.position_y_m * PIXELS_PER_METER);
		int vehicleY_logic = ourCarY_logic - CAR_HEIGHT_PX - dist_pixel;
		CRect rectVehicle(vehicleX_logic, vehicleY_logic, vehicleX_logic + CAR_WIDTH_PX, vehicleY_logic + CAR_HEIGHT_PX);

		CRect intersection;
		if (intersection.IntersectRect(&rectOurCar, &rectVehicle))
		{
			m_bHasCrashed = true;
			m_bIsRunning = false;
			m_dTTC = 0.0;
			m_nPrimaryTargetId = vehicle.id;
			return;
		}
	}

	// 后方碰撞预警(RCW)逻辑
	m_bRearCollisionWarning = false;
	LaneNeighborInfo currentLaneNeighbors = GetLaneNeighbors(m_nOurCarLane);
	if (currentLaneNeighbors.rearVehicleId != -1)
	{
		VehicleState* rearCar = GetVehicleById(currentLaneNeighbors.rearVehicleId);
		if (rearCar)
		{
			double relative_speed_ms = rearCar->speed_ms - m_dOurSpeed_ms;
			if (relative_speed_ms > 0)
			{
				double ttc_rear = -currentLaneNeighbors.rearVehicleDist_m / relative_speed_ms;
				if (ttc_rear < REAR_TTC_WARNING_S)
				{
					m_bRearCollisionWarning = true;
				}
			}
		}
	}

	// 前车碰撞逻辑 (基于物理位置)
	m_nPrimaryTargetId = -1;
	double minDistance = 1000.0;
	for (const auto& vehicle : m_trafficVehicles)
	{
		if (abs(vehicle.lateralPosition_px - m_dOurCarLateralPos_px) < CAR_WIDTH_PX && vehicle.position_y_m > 0)
		{
			if (vehicle.position_y_m < minDistance)
			{
				minDistance = vehicle.position_y_m;
				m_nPrimaryTargetId = vehicle.id;
			}
		}
	}

	// TTC计算逻辑
	VehicleState* target = GetVehicleById(m_nPrimaryTargetId);
	if (target)
	{
		double relative_speed_to_target = m_dOurSpeed_ms - target->speed_ms;
		if (relative_speed_to_target > 0) {
			m_dTTC = target->position_y_m / relative_speed_to_target;
		}
		else {
			m_dTTC = 999.0;
		}
	}
	else {
		m_dTTC = 999.0;
	}

	// 车辆标记销毁逻辑
	for (auto& vehicle : m_trafficVehicles)
	{
		if (vehicle.position_y_m < -150.0)
		{
			vehicle.toBeRemoved = true;
		}
	}
	m_trafficVehicles.erase(
		std::remove_if(m_trafficVehicles.begin(), m_trafficVehicles.end(),
			[](const VehicleState& v) {
				return v.toBeRemoved;
			}),
		m_trafficVehicles.end());
}


void CSimulationEngine::ChangeLaneLeft()
{
	if (m_nOurCarLane <= 0) return;

	int targetLane = m_nOurCarLane - 1;

	VehicleState tempPlayerState;
	tempPlayerState.id = 0;
	tempPlayerState.position_y_m = 0;
	tempPlayerState.speed_ms = m_dOurSpeed_ms;
	tempPlayerState.lateralPosition_px = m_dOurCarLateralPos_px;
	tempPlayerState.targetLaneIndex = m_nOurCarLane;

	if (IsLaneChangeSafe(tempPlayerState, targetLane))
	{
		m_laneChangeAdvice = LaneChangeAdvice::Safe;
		m_nOurCarLane = targetLane;
		m_dOurCarTargetLateralPos_px = (m_nOurCarLane - 1) * LANE_WIDTH_PX;
	}
	else
	{
		LaneNeighborInfo neighbors = GetLaneNeighbors(targetLane);
		if (neighbors.frontVehicleId != -1 && neighbors.frontVehicleDist_m < 30.0) {
			m_laneChangeAdvice = LaneChangeAdvice::Unsafe_FrontTooClose;
		}
		else {
			m_laneChangeAdvice = LaneChangeAdvice::Unsafe_RearTooClose;
		}
		m_laneChangeAdviceTimestamp = m_dScenarioTime;
	}
}

void CSimulationEngine::ChangeLaneRight()
{
	if (m_nOurCarLane >= LANE_COUNT - 1) return;

	int targetLane = m_nOurCarLane + 1;

	VehicleState tempPlayerState;
	tempPlayerState.id = 0;
	tempPlayerState.position_y_m = 0;
	tempPlayerState.speed_ms = m_dOurSpeed_ms;
	tempPlayerState.lateralPosition_px = m_dOurCarLateralPos_px;
	tempPlayerState.targetLaneIndex = m_nOurCarLane;

	if (IsLaneChangeSafe(tempPlayerState, targetLane))
	{
		m_laneChangeAdvice = LaneChangeAdvice::Safe;
		m_nOurCarLane = targetLane;
		m_dOurCarTargetLateralPos_px = (m_nOurCarLane - 1) * LANE_WIDTH_PX;
	}
	else
	{
		LaneNeighborInfo neighbors = GetLaneNeighbors(targetLane);
		if (neighbors.frontVehicleId != -1 && neighbors.frontVehicleDist_m < 30.0) {
			m_laneChangeAdvice = LaneChangeAdvice::Unsafe_FrontTooClose;
		}
		else {
			m_laneChangeAdvice = LaneChangeAdvice::Unsafe_RearTooClose;
		}
		m_laneChangeAdviceTimestamp = m_dScenarioTime;
	}
}

void CSimulationEngine::ExecuteAutomatedLaneChange(int targetLane)
{
	if (targetLane < 0 || targetLane >= LANE_COUNT) return;

	m_nOurCarLane = targetLane;
	m_dOurCarTargetLateralPos_px = (m_nOurCarLane - 1) * LANE_WIDTH_PX;
}


LaneNeighborInfo CSimulationEngine::GetLaneNeighbors(int targetLane) const
{
	LaneNeighborInfo neighbors;
	double targetLaneCenter_px = (targetLane - 1) * LANE_WIDTH_PX;

	for (const auto& vehicle : m_trafficVehicles)
	{
		if (abs(vehicle.lateralPosition_px - targetLaneCenter_px) > LANE_WIDTH_PX / 2.0)
		{
			continue;
		}

		if (vehicle.position_y_m > 0)
		{
			if (vehicle.position_y_m < neighbors.frontVehicleDist_m)
			{
				neighbors.frontVehicleDist_m = vehicle.position_y_m;
				neighbors.frontVehicleId = vehicle.id;
			}
		}
		else
		{
			if (abs(vehicle.position_y_m) < abs(neighbors.rearVehicleDist_m))
			{
				neighbors.rearVehicleDist_m = vehicle.position_y_m;
				neighbors.rearVehicleId = vehicle.id;
			}
		}
	}
	return neighbors;
}

void CSimulationEngine::SpawnVehicle()
{
	VehicleState newCar;
	newCar.id = m_nNextVehicleId;
	newCar.isCutInCar = false;
	newCar.state = VehicleState::Following;
	newCar.nextState = VehicleState::Following;
	newCar.position_y_m = 300.0;

	std::uniform_int_distribution<int> lane_dist(0, LANE_COUNT - 1);
	int lane = lane_dist(m_rng);
	newCar.targetLaneIndex = lane;

	std::uniform_real_distribution<double> speed_dist(80.0 / 3.6, 110.0 / 3.6);
	newCar.speed_ms = speed_dist(m_rng);

	std::uniform_real_distribution<double> change_time_dist(5.0, 15.0);
	newCar.nextLaneChangeCheckTime_s = m_dScenarioTime + change_time_dist(m_rng);

	double targetLaneCenter_px = (lane - 1) * LANE_WIDTH_PX;
	newCar.lateralPosition_px = targetLaneCenter_px;
	newCar.originalLaneIndex = -1; // 普通车没有原始车道概念

	for (const auto& v : m_trafficVehicles) {
		bool isLaterallyClose = abs(v.lateralPosition_px - targetLaneCenter_px) < LANE_WIDTH_PX / 2.0;
		bool isLongitudinallyClose = abs(v.position_y_m - newCar.position_y_m) < 100.0;
		if (isLaterallyClose && isLongitudinallyClose) {
			return;
		}
	}

	m_trafficVehicles.push_back(newCar);
	m_nNextVehicleId++;
}
bool CSimulationEngine::IsLaneChangeSafe(const VehicleState& movingVehicle, int targetLane) const
{
	const double SAFE_TTC_THRESHOLD = 4.0;
	const double MIN_SAFE_DISTANCE_M = 15.0;

	// 创建一个包含所有其他车辆的列表，用于进行碰撞检测
	VehicleState playerVehicle;
	playerVehicle.id = 0;
	playerVehicle.position_y_m = 0;
	playerVehicle.speed_ms = m_dOurSpeed_ms;
	playerVehicle.lateralPosition_px = m_dOurCarLateralPos_px;
	playerVehicle.targetLaneIndex = m_nOurCarLane;

	std::vector<const VehicleState*> world;
	if (movingVehicle.id != 0)
	{
		world.push_back(&playerVehicle);
	}
	for (const auto& v : m_trafficVehicles)
	{
		if (v.id != movingVehicle.id)
		{
			world.push_back(&v);
		}
	}

	// 遍历所有其他车辆
	for (const auto* otherVehicle : world)
	{
		// 计算与我车（movingVehicle）的纵向距离
		double longitudinalDist = otherVehicle->position_y_m - movingVehicle.position_y_m;
		if (movingVehicle.id == 0) { // 如果是我车在变道
			longitudinalDist = otherVehicle->position_y_m;
		}
		else if (otherVehicle->id == 0) { // 如果是AI车辆在变道，检测与我车的关系
			longitudinalDist = -movingVehicle.position_y_m;
		}
		// 判定标准：只要另一辆车的位置在目标车道内（允许一定误差），就必须进行严格的安全检查
		double targetLaneCenter_px = (targetLane - 1) * LANE_WIDTH_PX;
		double lateralDistFromTargetLaneCenter_px = abs(otherVehicle->lateralPosition_px - targetLaneCenter_px);

		// 如果车辆的侧向位置在目标车道内，则视为潜在威胁
		if (lateralDistFromTargetLaneCenter_px < LANE_WIDTH_PX / 2.0)
		{
			// 检查1: 最小物理距离（例如，盲区里有车）
			if (abs(longitudinalDist) < MIN_SAFE_DISTANCE_M)
			{
				return false; // 不安全
			}

			// 检查2: 基于时间的碰撞检查 (TTC)
			double relativeSpeed = movingVehicle.speed_ms - otherVehicle->speed_ms;

			// 情况A: 我车更快，正在接近前方的它
			if (relativeSpeed > 0 && longitudinalDist > 0)
			{
				double ttc = longitudinalDist / relativeSpeed;
				if (ttc < SAFE_TTC_THRESHOLD) return false; // TTC太小，不安全
			}
			// 情况B: 它更快，正在从后方接近我车
			else if (relativeSpeed < 0 && longitudinalDist < 0)
			{
				double ttc = longitudinalDist / relativeSpeed; // 两个负数相除，TTC为正
				if (ttc < SAFE_TTC_THRESHOLD) return false; // 它追尾我车的TTC太小，不安全
			}
		}
	}

	// 如果遍历完所有车辆都没有发现危险，则变道是安全的
	return true;
}

void CSimulationEngine::SetRunning(bool isRunning) { m_bIsRunning = isRunning; }
void CSimulationEngine::SetAccStatus(bool isOn) { m_bAccOn = isOn; }
void CSimulationEngine::SetDesiredTimeGap(double timeGap) { if (timeGap > 0.5) m_dDesiredTimeGap_s = timeGap; }
double CSimulationEngine::GetOurCarLateralPos_px() const { return m_dOurCarLateralPos_px; }
double CSimulationEngine::GetOurSpeed_ms() const { return m_dOurSpeed_ms; }
double CSimulationEngine::GetTTC() const { return m_dTTC; }
double CSimulationEngine::GetDesiredTimeGap() const { return m_dDesiredTimeGap_s; }
double CSimulationEngine::GetScenarioTime() const { return m_dScenarioTime; }
bool CSimulationEngine::IsRunning() const { return m_bIsRunning; }
bool CSimulationEngine::HasCrashed() const { return m_bHasCrashed; }
bool CSimulationEngine::IsAccOn() const { return m_bAccOn; }
int CSimulationEngine::GetOurCarLane() const { return m_nOurCarLane; }
const std::vector<VehicleState>& CSimulationEngine::GetTrafficVehicles() const { return m_trafficVehicles; }
bool CSimulationEngine::IsRearCollisionWarningActive() const { return m_bRearCollisionWarning; }
int CSimulationEngine::GetPrimaryTargetId() const { return m_nPrimaryTargetId; }
CSimulationEngine::LaneChangeAdvice CSimulationEngine::GetLaneChangeAdvice() const { return m_laneChangeAdvice; }

double CSimulationEngine::GetDistance() const
{
	if (m_nPrimaryTargetId != -1) {
		for (const auto& v : m_trafficVehicles) {
			if (v.id == m_nPrimaryTargetId) {
				return v.position_y_m;
			}
		}
	}
	return 999.0;
}

double CSimulationEngine::GetPrimaryTargetSpeed_ms() const
{
	if (m_nPrimaryTargetId != -1) {
		for (const auto& v : m_trafficVehicles) {
			if (v.id == m_nPrimaryTargetId) {
				return v.speed_ms;
			}
		}
	}
	return 0.0;
}

VehicleState* CSimulationEngine::GetVehicleById(int id)
{
	if (id == -1) return nullptr;
	for (auto& vehicle : m_trafficVehicles)
	{
		if (vehicle.id == id)
		{
			return &vehicle;
		}
	}
	return nullptr;
}
