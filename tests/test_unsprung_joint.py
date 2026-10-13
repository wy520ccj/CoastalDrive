"""同一十六维质量/真实接触虚功与有限端口的共同末状态验证。"""

from dataclasses import replace

import numpy as np
import pytest
from test_unsprung_dynamics import CENTERS, GUIDES, LOCKED

from suspension import stiffness_matrix
from unsprung_drivetrain import drivetrain_ports, tire_ports
from unsprung_dynamics import assemble_unsprung, partition_vehicle
from unsprung_joint import solve_unsprung_joint
from vehicle_designs import REFERENCE_DESIGN
from wheel_geometry import mechanical_axis


def hardware(config, steering=0., body_speed=None, trail=.02, steer_rate=0., ratio=3.2):
    partition = partition_vehicle(config.mass,LOCKED,(40.,)*4,CENTERS)
    mechanical = assemble_unsprung(partition,np.eye(3),np.zeros(4),GUIDES,
                                   np.zeros(10) if body_speed is None else body_speed)
    axes = np.array([mechanical_axis((1.,0.,0.),(0.,1.,0.),steering if i<2 else 0.) for i in range(4)])
    graph = drivetrain_ports(mechanical,axes,(0.,1.,0.),(0.,1.,0.),((0.,1.,0.),)*3,ratio,config)
    normals = np.array(GUIDES)
    tangents = np.cross(normals,axes)
    laterals = np.cross(tangents,normals)
    contacts = tire_ports(graph,-.33*normals,tangents,laterals,normals,
                          ((0.,0.,steer_rate),)*2+((0.,0.,0.),)*2,(trail,)*4)
    return graph,contacts,partition


def solve(config, speed=20., steering=3., brake=(120.,120.,80.,80.), ratio=3.2,
          sync=False, capacity=100., road=(0.,)*4, airborne=False, spin_offsets=(0.,)*4,
          old_down_offset=(0.,)*3):
    graph,contacts,partition = hardware(config,steering,steer_rate=-.2,ratio=ratio)
    state = np.zeros(16)
    state[1],state[10],state[12:] = speed,250.,speed/.33
    state[12:] += spin_offsets
    state[11] = graph.output@state
    downstream = graph.downstream@state+old_down_offset
    ks = np.asarray(stiffness_matrix(config.suspension_spring_rates,config.suspension_antiroll_rates))
    compression = np.linalg.solve(ks,np.full(4,partition.mass*9.81/4))
    radial = np.full(4,200000.)
    deflection = (ks@compression+40*9.81)/radial
    if airborne:
        deflection = np.full(4,-.5)
        compression = np.zeros(4)
    known = np.r_[graph.mechanical.gravity_forces((0.,0.,-9.81)),np.zeros(6)]
    result = solve_unsprung_joint(graph,contacts,state,downstream,compression,deflection,np.zeros((4,2)),np.zeros((4,2)),
        known,road,radial,np.full(4,500.),np.full(4,.7),np.full(4,.013),50.,.12,capacity,brake,ratio,sync,1/240,config)
    return result,graph,contacts,state,downstream,known,compression,deflection


@pytest.mark.parametrize("share", [0.,.5,1.])
def test_mass_and_port_energy_keeps_unsprung_and_real_rotor_storage(share):
    config = replace(REFERENCE_DESIGN,front_drive_share=share)
    graph,_contacts,p = hardware(config,steering=12.)
    state = np.array((.2,12.,-.1,.1,-.2,.3,.2,-.1,.1,-.2,200.,180.,36.,37.,39.,40.))
    wheels = graph.mechanical.wheel_jacobians@state[:10]
    physical = (.5*p.mass*np.dot(state[:3],state[:3])+.5*state[3:6]@graph.mechanical.world_inertia@state[3:6]
                +.5*np.sum(np.asarray(p.wheel_masses)[:,None]*wheels**2)
                +.5*config.engine_inertia*state[10]**2+.5*config.input_shaft_inertia*state[11]**2
                +.5*config.wheel_inertia*np.dot(state[12:],state[12:]))
    relative = state[12:]+graph.axes@state[3:6]
    weights = ((share/2,share/2,(1-share)/2,(1-share)/2),(.5,.5,0.,0.),(0.,0.,.5,.5))
    downstream = np.array([np.dot(axis,state[3:6])+config.final_drive*np.dot(w,relative)
                           for axis,w in zip(graph.downstream_axes,weights)])
    physical += .5*np.dot(graph.downstream_inertias,downstream**2)
    assert .5*state@graph.mass@state == pytest.approx(physical,abs=4e-11)
    assert graph.brakes@state == pytest.approx(relative,abs=1e-14)
    assert graph.gear@state == pytest.approx(state[11]-np.dot(graph.shaft_axis,state[3:6])-graph.output@state,abs=1e-13)
    assert np.linalg.eigvalsh(graph.mass)[0]>0.


def test_surface_virtual_power_includes_wheel_travel_camber_and_steering():
    graph,_contacts,_p = hardware(REFERENCE_DESIGN)
    angle = .17
    axes = np.array(((np.cos(angle),0.,np.sin(angle)),)*4)
    graph = replace(graph,axes=axes,brakes=graph.brakes.copy())
    graph.brakes[:,3:6] = axes
    normals = np.array(GUIDES)
    tangents = np.array(((0.,1.,0.),)*4)
    laterals = np.cross(tangents,normals)
    steering = np.array(((0.,0.,-.3),)*4)
    offset = -.33*normals
    trail = .025
    contacts = tire_ports(graph,offset,tangents,laterals,normals,steering,(trail,)*4)
    state = np.array((.3,20.,-.2,.1,-.2,.3,.2,-.1,.1,-.2,200.,180.,60.,62.,58.,64.))
    for i in range(4):
        for row,direction,component in ((contacts.longitudinal[i],tangents[i],0),
                                        (contacts.lateral[i],laterals[i],1),(contacts.normal[i],normals[i],2)):
            point_offset = offset[i]-trail*tangents[i] if component==1 else offset[i]
            hub_speed = state[:3]+np.cross(state[3:6],graph.mechanical.wheel_arms[i])+graph.mechanical.guides[i]*state[6+i]
            relative_spin = state[12+i]+np.dot(state[3:6],axes[i])
            surface = hub_speed+np.cross(state[3:6]+steering[i]-relative_spin*axes[i],point_offset)
            assert row@state+contacts.steering_velocity[i,component] == pytest.approx(np.dot(direction,surface),abs=1e-14)
    assert np.any(np.abs(contacts.spin_radii[:,1])>0.)  # 外倾拖距的轴向分量不能遗漏。


@pytest.mark.parametrize("share,ratio,sync,airborne", [(0.,3.2,False,False),(.5,3.2,False,False),
    (1.,-3.2,False,False),(0.,0.,False,True),(0.,3.2,True,False)])
def test_full_joint_keeps_real_load_and_finite_drive_brake_energy(share,ratio,sync,airborne):
    config = replace(REFERENCE_DESIGN,front_drive_share=share)
    result,graph,contacts,start,old_down,known,_q0,_delta0 = solve(config,ratio=ratio,sync=sync,airborne=airborne)
    assert result.momentum_error<1e-9 and result.force_error<1e-5 and result.port_error<1e-9
    assert result.energy_error == pytest.approx(0.,abs=3e-8)
    assert result.port_heat.min()>-1e-8 and result.road_loss>=0. and result.rolling_heat>=0.
    assert max(abs(result.port_torques[3:7]))<=120.+1e-9
    assert abs(result.port_torques[0])<=100.+1e-9
    for i,wheel in enumerate(result.wheels):
        assert np.hypot(wheel.fx,wheel.fy)<=result.force_parameters[i,0]+np.sqrt(2)*result.force_error
        assert wheel.relative_omega == pytest.approx(graph.brakes[i]@result.velocity,abs=1e-12)
    if airborne:
        assert np.max(result.normal.normal_force) == 0.
        assert np.max(np.abs(result.forces))<1e-5
    elif not sync and ratio:
        assert graph.gear@result.velocity == pytest.approx(0.,abs=1e-11)
    # 对整个质量方程独立展开已知/发动机/接触/端口/陀螺反力。
    end = result.velocity
    gs = np.zeros((4,16))
    gs[:,6:10] = np.eye(4)
    ports = np.vstack((graph.clutch,graph.gear,graph.output,graph.brakes,graph.differential))
    force = known+50.*graph.engine-.12*(graph.engine@end)*graph.engine
    force += -gs.T@result.normal.suspension_force+contacts.normal.T@result.normal.normal_force
    force += contacts.longitudinal.T@result.forces[:,0]+contacts.lateral.T@result.forces[:,1]-ports.T@result.port_torques
    force[12:] -= result.rolling_torques
    force[3:6] -= np.cross(end[3:6],graph.spin(end,config))
    assert graph.mass@end-graph.initial_momentum(start,old_down) == pytest.approx(force/240.,abs=1e-9)


@pytest.mark.parametrize("case", ["reverse","lsd","rough","stored_rotor"])
def test_reverse_lsd_rough_load_and_prior_actual_rotor_state_have_closed_energy(case):
    config = REFERENCE_DESIGN
    options = {}
    if case=="reverse":
        options.update(speed=-20.,ratio=-3.2)
    elif case=="lsd":
        config = replace(config,front_drive_share=.5,differential_damping=(25.,30.,10.),
                         differential_capacity=(80.,80.,100.),axle_torque_bias_ratios=(2.,3.))
        options.update(spin_offsets=(-2.,2.,-3.,3.))
    elif case=="rough":
        options.update(road=(.003,0.,0.,-.003))
    else:
        options.update(old_down_offset=(10.,-5.,3.))
    result,graph,contacts,start,old_down,known,q0,delta0 = solve(config,**options)
    end,dt = result.velocity,1/240
    assert result.energy_error == pytest.approx(0.,abs=3e-8)
    assert result.port_heat.min()>-1e-8
    if case=="lsd":
        assert np.max(np.abs(result.port_torques[7:]))>1.
    if case=="rough":
        assert np.ptp(result.normal.normal_force)>100.
        assert np.max(np.abs(end[6:10]))>.001
    if case=="stored_rotor":
        assert np.max(np.abs(result.downstream_omega-old_down))>1.

    def kinetic(state, downstream):
        mechanical = graph.mechanical
        wheel_velocities = np.array([state[:3]+np.cross(state[3:6],r)+mechanical.guides[i]*state[6+i]
                                     for i,r in enumerate(mechanical.wheel_arms)])
        return (.5*mechanical.sprung_mass*np.dot(state[:3],state[:3])
                +.5*state[3:6]@mechanical.world_inertia@state[3:6]
                +.5*np.sum(mechanical.wheel_masses[:,None]*wheel_velocities**2)
                +.5*config.engine_inertia*state[10]**2+.5*config.input_shaft_inertia*state[11]**2
                +.5*config.wheel_inertia*np.dot(state[12:],state[12:])
                +.5*np.dot(graph.downstream_inertias,downstream**2))

    def suspension_energy(q):
        return (sum(.5*k*x*x for k,x in zip(config.suspension_spring_rates,q))
                +sum(.5*k*(q[i]-q[i+1])**2 for i,k in zip((0,2),config.suspension_antiroll_rates))
                +sum(.5*k*max(abs(x)-config.suspension_travel,0.)**2 for k,x in zip(config.suspension_stop_rates,q)))

    k_change = kinetic(end,result.downstream_omega)-kinetic(start,old_down)
    k_discrete = kinetic(end-start,result.downstream_omega-old_down)
    delta,q = result.tire_deflection,result.compression
    u_change = suspension_energy(q)-suspension_energy(q0)+.5*200000.*np.sum(np.maximum(delta,0.)**2-np.maximum(delta0,0.)**2)
    u_change += .5*config.tire_contact_stiffness*sum(w.deformation_x**2+w.deformation_y**2 for w in result.wheels)
    tire_loss = sum(w.material_dissipation+w.road_dissipation+w.elastic_numerical_dissipation for w in result.wheels)
    damping = np.where(end[6:10]>=0.,config.suspension_compression_damping,config.suspension_extension_damping)
    suspension_loss = dt*np.dot(damping,end[6:10]**2)
    spring = np.asarray(stiffness_matrix(config.suspension_spring_rates,config.suspension_antiroll_rates))@q
    spring += np.asarray(config.suspension_stop_rates)*(q-np.clip(q,-config.suspension_travel,config.suspension_travel))
    suspension_numeric = np.dot(spring,q-q0)-(suspension_energy(q)-suspension_energy(q0))
    radial_loss = np.dot(result.normal.normal_force,delta-delta0)-.5*200000.*np.sum(np.maximum(delta,0.)**2-np.maximum(delta0,0.)**2)
    ports = np.vstack((graph.clutch,graph.gear,graph.output,graph.brakes,graph.differential))
    friction_work = dt*np.dot(result.port_torques,ports@end)+dt*np.dot(result.rolling_torques,end[12:])
    engine_work = dt*50.*(end[10]-np.dot(end[3:6],graph.engine_axis))
    engine_heat = dt*.12*(end[10]-np.dot(end[3:6],graph.engine_axis))**2
    contact_force = np.column_stack((result.forces,result.normal.normal_force))
    input_work = dt*np.dot(end,known)-dt*np.sum(contact_force*contacts.steering_velocity)
    input_work += np.dot(result.normal.normal_force,options.get("road",(0.,)*4))
    assert (k_change+k_discrete+u_change+tire_loss+suspension_loss+suspension_numeric+radial_loss
            +friction_work+engine_heat-engine_work-input_work) == pytest.approx(0.,abs=3e-8)


def test_saved_actual_prepared_input_replays_complete_joint_prediction():
    import json
    from pathlib import Path

    from vehicle_parameters import config_from_document

    folder = Path(__file__).resolve().parents[1]/"docs/evidence/SIM-UNSPRUNG-01/joint-powered-complete"
    source = json.loads((folder/"source-input.json").read_text(encoding="utf-8"))
    expected = json.loads((folder/"prediction.json").read_text(encoding="utf-8"))
    config = config_from_document(source["config"],REFERENCE_DESIGN)
    partition = partition_vehicle(config.mass,source["body_inertia_local"],source["wheel_masses"],source["wheel_centers_local"])
    mechanical = assemble_unsprung(partition,source["rotation"],source["displacement"],source["guides_local"],source["new_initial_velocity"][:10])
    graph = drivetrain_ports(mechanical,source["axes"],source["engine_axis"],source["shaft_axis"],source["downstream_axes"],source["ratio"],config)
    contact = tire_ports(graph,source["offsets"],source["tangents"],source["laterals"],source["normals"],source["steering_angular"],source["trails"])
    result = solve_unsprung_joint(graph,contact,source["new_initial_velocity"],source["downstream_omega"],source["compression"],
        source["radial_deflection"],source["deformation"],source["initial_force"],source["known_force"],source["road_delta"],
        source["radial_rates"],source["radial_damping"],source["friction"],source["rolling_coefficients"],source["engine_torque"],
        source["engine_drag"],source["clutch_capacity"],source["brake_capacities"],source["ratio"],source["synchronizing"],source["dt"],config)
    assert result.velocity == pytest.approx(expected["velocity"],abs=1e-13)
    assert result.forces == pytest.approx(np.asarray(expected["forces"]),abs=1e-9)
    assert result.port_torques == pytest.approx(expected["port_torques"],abs=1e-9)
    assert result.energy_error == pytest.approx(0.,abs=3e-8)
    assert source["ratio"]!=0. and source["clutch_capacity"]>0. and max(source["brake_capacities"])>0.
