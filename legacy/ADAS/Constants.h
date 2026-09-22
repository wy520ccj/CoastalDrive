// Constants.h

#pragma once

// ===== 仿真参数常量 =====
const int    SIM_TIMER_INTERVAL_MS = 100;      // 仿真定时器间隔 (毫秒)
const double SIM_TIME_STEP_S = SIM_TIMER_INTERVAL_MS / 1000.0; // 仿真步长时间 (秒)
const int    MAX_SPEED_KMH = 220;            // 最大速度 (km/h)
const double INITIAL_DISTANCE_M = 50.0;        // 初始车距 (米)
const int    INITIAL_OUR_SPEED_KMH = 90;       // 初始我车速度 (km/h)
const int    INITIAL_FRONT_SPEED_KMH = 120;     // 初始前车速度 (km/h)
const double TTC_WARNING = 2.5;                // TTC预警阈值 (秒)
const double REAR_TTC_WARNING_S = 4.0;         //后车预警阈值

// ===== 物理模型常量 =====
const double MAX_ACCELERATION_MS2 = 3.0;     // 最大加速度 (米/秒^2)
const double MAX_DECELERATION_MS2 = 8.0;     // 最大减速度 (米/秒^2)
const double ACC_PROPORTIONAL_GAIN = 5.0;	 // ACC比例控制器增益
const double LANE_CHANGE_SPEED_PX_PER_S = 45.0; //变道速度(45像素 / 秒)
const double BRAKE_CHECK_DECELERATION_MS2 = 2.0; //切入后刹车的减速度(m / s ^ 2)

// ===== 绘图参数常量 =====
const int    CAR_WIDTH_PX = 40;                // 车辆宽度 (像素)
const int    CAR_HEIGHT_PX = 80;               // 车辆高度 (像素)
const int    CAR_BOTTOM_MARGIN_PX = 20;        // 我车底部边距 (像素)
const double PIXELS_PER_METER = 5.0;           // 比例尺 (像素/米)
const int    LANE_COUNT = 3;                   // 道路的车道数量
const int    LANE_WIDTH_PX = 90;			   // 每条车道的宽度(像素
