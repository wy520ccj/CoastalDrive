"""Vehicle dimensions are metres; steering angles are degrees."""

from dataclasses import dataclass


@dataclass(frozen=True)
class VehicleConfig:
    mass: float = 1200.0
    # Approximate 2-litre petrol engine, five-speed automatic. These are game tuning data.
    torque_curve: tuple = (
        (900, 110),
        (1800, 165),
        (3200, 200),
        (4500, 190),
        (6000, 150),
        (6500, 0),
    )
    gear_ratios: tuple = (3.25, 2.05, 1.45, 1.10, 0.88)
    final_drive: float = 3.7
    drivetrain_efficiency: float = 0.88
    idle_rpm: float = 900.0
    shift_time: float = 0.28
    throttle_rise: float = 1.6  # Full pedal travel per second, for a held keyboard key.
    throttle_release: float = 5.0
    brake_rise: float = 6.0
    brake_release: float = 10.0
    torque_response: float = 0.12
    engine_braking: float = 24.0  # Approximate closed-throttle torque at the crank, Nm.
    max_speed: float = 160 / 3.6
    reverse_speed: float = 22 / 3.6
    reverse_force: float = 2200.0
    brake_torque: float = 3643.2  # Total wheel braking torque, Nm.
    front_brake_share: float = 0.60
    reverse_delay: float = 0.4
    steering_degrees: float = 26.0
    steering_rate: float = 50.0
    steering_response: float = 7.0
    steering_return: float = 10.0
    assisted_lateral_acceleration: float = 7.5  # Keyboard steering envelope, m/s².
    wheel_radius: float = 0.33
    suspension_stiffness: float = 40.0
    suspension_compression: float = 4.4
    suspension_relaxation: float = 2.3
    road_grip: float = 1.4
    grass_grip: float = 0.8
    air_density: float = 1.225  # kg/m³
    drag_coefficient: float = 0.32
    frontal_area: float = 2.142857142857143  # m²; preserves the previous Cd*A product.
    rolling_coefficient: float = 160 / (1200 * 9.81)
    grass_rolling_coefficient: float = 900 / (1200 * 9.81)
    road_friction: float = 1.1
    grass_friction: float = 0.45
    wheelbase: float = 2.2
    track_width: float = 1.68
    center_of_mass_height: float = 0.42
    front_weight_share: float = 0.5


CAR = VehicleConfig()
WHEEL_HUBS = tuple(
    (side * CAR.track_width / 2, axle * CAR.wheelbase / 2, 0.25)
    for axle in (1, -1)
    for side in (-1, 1)
)
