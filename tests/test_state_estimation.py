"""解析三维运动、延迟回放等价及偏置/轮滑/失联的短独立检查。"""

from dataclasses import replace

import numpy as np

from estimation_rotation import conjugate, exp, log, matrix, multiply
from sensor_sampling import DT, ImuSample, SensorConfig, SensorSuite, TruthSample
from state_estimation import EstimatorTimeline, VehicleEstimator, imu_jacobians

HUBS = np.array(((-.76, 1.21, .18), (.76, 1.21, .18), (-.775, -1.365, .18), (.775, -1.365, .18)))
RADIUS = .3146
OMEGA = np.array((.08, .04, .12))
ACCELERATION = np.array((.2, .4, .05))
INITIAL_VELOCITY = np.array((.3, 8., .1))


def truth(tick, slip=False):
    time = tick * DT
    orientation = exp(OMEGA * time)
    velocity = INITIAL_VELOCITY + ACCELERATION * time
    position = INITIAL_VELOCITY * time + .5 * ACCELERATION * time**2
    steering = np.array((.10, .11, 0., 0.))
    tangents = np.column_stack((np.sin(steering), np.cos(steering), np.zeros(4)))
    points = matrix(orientation).T @ velocity + np.cross(OMEGA, HUBS)
    wheel_omega = np.sum(points * tangents, axis=1) / RADIUS
    if slip:
        wheel_omega[2:] *= 1.8
    return TruthSample(tick, tuple(position), tuple(velocity), tuple(orientation), tuple(wheel_omega), tuple(steering))


def run(config, ticks, exact=False, slipping=False):
    suite = SensorSuite(truth(0), config, seed=41)
    initial_position = (0., 0., 0.) if exact else (.5, -.4, .2)
    initial_velocity = INITIAL_VELOCITY if exact else INITIAL_VELOCITY + (.1, -.15, .04)
    estimator = VehicleEstimator(initial_position, initial_velocity, exp((0., 0., 0.)), RADIUS, HUBS, config)
    timeline = EstimatorTimeline(estimator)
    position_errors, velocity_errors, rejected, observed_errors = [], [], 0, []
    for tick in range(1, ticks + 1):
        true = truth(tick, slipping and 480 <= tick < 600)
        frame = suite.sample(true)
        result = timeline.advance(frame)
        if tick >= 120:
            position_errors.append(np.asarray(result.position) - true.position)
            velocity_errors.append(np.asarray(result.velocity) - true.velocity)
        if frame.wheels is not None and result.wheel_accepted is False and 480 <= tick < 600:
            rejected += 1
        for sample in frame.gnss:
            observed_errors.append(np.asarray(sample.position) - truth(sample.tick).position)
    metrics = {"position_rmse_m": float(np.sqrt(np.mean(np.asarray(position_errors)**2))),
               "velocity_rmse_m_s": float(np.sqrt(np.mean(np.asarray(velocity_errors)**2))),
               "orientation_error_rad": float(np.linalg.norm(log(multiply(conjugate(true.orientation), result.orientation)))),
               "minimum_covariance_eigenvalue": float(np.linalg.eigvalsh(estimator.covariance).min()),
               "slipping_wheel_rejections": rejected,
               "gnss_position_rmse_m": float(np.sqrt(np.mean(np.asarray(observed_errors)**2))) if observed_errors else None}
    return result, estimator.covariance, metrics



def test_noiseless_imu_recovers_independent_three_dimensional_motion():
    quiet = SensorConfig(accel_sample_std=0., gyro_sample_std=0., accel_bias_walk=0., gyro_bias_walk=0.,
                         initial_accel_bias=(0.,) * 3, initial_gyro_bias=(0.,) * 3,
                         wheel_omega_std=0., steering_std_rad=0., wheel_period_ticks=1000,
                         gnss_outages=((0, 10000),))
    _result, _covariance, metrics = run(quiet, 240, exact=True)
    assert metrics['position_rmse_m'] < 1e-11
    assert metrics['velocity_rmse_m_s'] < 1e-11
    assert metrics['orientation_error_rad'] < 1e-12


def test_delayed_gnss_replays_to_identical_full_estimate_and_covariance():
    config = SensorConfig(gnss_delay_ticks=0, gnss_outages=((229, 10000),))
    instant, covariance, _metrics = run(config, 240)
    delayed, delayed_covariance, _metrics = run(replace(config, gnss_delay_ticks=12), 240)
    assert instant == delayed
    assert np.array_equal(covariance, delayed_covariance)


def test_bias_noise_gnss_outage_and_wheel_slip_keep_a_real_independent_estimate():
    _result, _covariance, metrics = run(SensorConfig(gnss_outages=((360, 720),)), 960, slipping=True)
    assert metrics['minimum_covariance_eigenvalue'] >= -1e-12
    assert metrics['position_rmse_m'] < metrics['gnss_position_rmse_m']
    assert metrics['velocity_rmse_m_s'] < .2
    assert metrics['slipping_wheel_rejections'] == 60


def test_midpoint_error_jacobian_matches_independent_state_perturbations():
    orientation = exp((.2, -.1, .3))
    specific, omega = np.array((.5, -.3, 9.4)), np.array((.4, -.2, .3))
    sample = ImuSample(1, tuple(specific), tuple(omega))
    nominal = VehicleEstimator((1., 2., 3.), (.3, 4., .1), orientation, RADIUS, HUBS)
    nominal.predict(sample)
    columns = []
    for coordinate in range(15):
        outputs = []
        for sign in (-1, 1):
            delta = np.eye(15)[coordinate] * sign * 1e-5
            perturbed = VehicleEstimator(np.array((1., 2., 3.)) + delta[:3],
                np.array((.3, 4., .1)) + delta[3:6], multiply(orientation, exp(delta[6:9])), RADIUS, HUBS)
            perturbed.accel_bias += delta[9:12]
            perturbed.gyro_bias += delta[12:15]
            perturbed.predict(sample)
            outputs.append(np.r_[perturbed.position - nominal.position, perturbed.velocity - nominal.velocity,
                log(multiply(conjugate(nominal.orientation), perturbed.orientation)), perturbed.accel_bias, perturbed.gyro_bias])
        columns.append((outputs[1] - outputs[0]) / 2e-5)
    analytic = imu_jacobians(orientation, specific, omega)[0]
    assert np.max(np.abs(np.array(columns).T - analytic)) < 1e-8


def test_stationary_tilted_imu_measures_specific_gravity_and_zero_rotation():
    config = SensorConfig(accel_sample_std=0., gyro_sample_std=0., accel_bias_walk=0., gyro_bias_walk=0.,
                         initial_accel_bias=(0.,) * 3, initial_gyro_bias=(0.,) * 3)
    orientation = exp((.3, -.2, .1))
    initial = TruthSample(0, (0.,) * 3, (0.,) * 3, tuple(orientation), (0.,) * 4, (0.,) * 4)
    sample = SensorSuite(initial, config).sample(replace(initial, tick=1))
    assert np.allclose(sample.imu.specific_force, matrix(orientation).T @ (0., 0., 9.81), atol=1e-12)
    assert np.linalg.norm(sample.imu.angular_velocity) < 1e-12
