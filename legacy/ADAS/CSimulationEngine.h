// CSimulationEngine.h

#pragma once
#include <vector>
#include <random>

// 通用车辆状态结构体
struct VehicleState
{
	int    id;              // 车辆唯一ID
	double position_y_m;    // 纵向位置（相对于我车）
	double speed_ms;        // 速度 (米/秒)
	int    targetLaneIndex; // 目标车道
	double lateralPosition_px; // 车辆相对于“道路中心线”的精确横向偏移（像素）
	bool   isCutInCar;      // 是否是切入车辆的特殊标记
	int    originalLaneIndex; // 记录车辆的初始车道
	double stateChangeTimestamp; //记录进入某个状态的时间戳
	double cooldownEndTime_s; // 记录冷却状态的结束时间
	double nextLaneChangeCheckTime_s;
	int nextTargetLaneIndex; // 记录车辆“下一步”想去的车道
	bool toBeRemoved = false;

	// 车辆在场景中的行为状态
	enum BehaviorState { Following, CuttingIn, Stabilizing, Braking, PreparingToCutIn, ReturningToLane, ChangingLane } state;
	BehaviorState nextState;
};
//描述一个车道内的邻近车辆情况
struct LaneNeighborInfo
{
	int frontVehicleId = -1; // 前方最近车辆的ID
	double frontVehicleDist_m = 9999.0; // 与前方车辆的距离
	int rearVehicleId = -1;  // 后方最近车辆的ID
	double rearVehicleDist_m = 9999.0;  // 与后方车辆的距离 (负数表示在后方)
};

class CSimulationEngine
{
public:
	// 构造函数
	CSimulationEngine();

	//枚举
	enum LaneChangeAdvice { Safe, Unsafe_RearTooClose, Unsafe_FrontTooClose };

	// 核心公共接口
	void Reset();
	void Update(double timeStep, double acceleration_ms2, const CRect& rectScene);

	// Setters
	void SetRunning(bool isRunning);
	void SetAccStatus(bool isOn);
	void SetDesiredTimeGap(double timeGap);
	// Getters)
	double GetOurSpeed_ms() const;
	double GetDistance() const;
	double GetTTC() const;
	double GetDesiredTimeGap() const;
	double GetScenarioTime() const;
	bool IsRunning() const;
	bool HasCrashed() const;
	bool IsAccOn() const;
	int GetOurCarLane() const;
	const std::vector<VehicleState>& GetTrafficVehicles() const;
	int GetPrimaryTargetId() const;
	double GetPrimaryTargetSpeed_ms() const;
	double GetOurCarLateralPos_px() const;
	bool IsRearCollisionWarningActive() const;
	LaneChangeAdvice GetLaneChangeAdvice() const;
	//变道
	void ChangeLaneLeft();
	void ChangeLaneRight();
	LaneNeighborInfo GetLaneNeighbors(int targetLane) const;//感知邻近车辆
	void ExecuteAutomatedLaneChange(int targetLane);
	//丰富车流
	void SpawnVehicle();
	bool IsLaneChangeSafe(const VehicleState& movingVehicle, int targetLane) const;
	VehicleState* GetVehicleById(int id);
private:
	// 内部状态变量
	double m_dOurSpeed_ms;
	int m_nOurCarLane;
	double m_dOurCarLateralPos_px;      // 我车当前的精确横向位置（像素偏移）
	double m_dOurCarTargetLateralPos_px; // 我车的目标横向位置（像素偏移）
	std::vector<VehicleState> m_trafficVehicles;
	LaneChangeAdvice m_laneChangeAdvice;
	bool m_bRearCollisionWarning;
	int m_nPrimaryTargetId;
	double m_laneChangeAdviceTimestamp;
	double m_dTTC;
	bool   m_bIsRunning;
	bool   m_bHasCrashed;
	bool   m_bAccOn;
	double m_dDesiredTimeGap_s;
	double m_dScenarioTime;
	std::mt19937 m_rng;
	double m_dCutInTriggerTime_s;
	double m_dNextSpawnTime_s; // 下一辆车生成的时间
	int m_nNextVehicleId;      // 用于为新车分配唯一的ID
};
