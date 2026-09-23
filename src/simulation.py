"""Fixed-step world, shared vehicles, traffic lifecycle and read-only snapshots."""

import math
import random
from dataclasses import dataclass, replace

from panda3d.bullet import (
    BulletBoxShape,
    BulletPlaneShape,
    BulletRigidBodyNode,
    BulletSphereShape,
    BulletTriangleMesh,
    BulletTriangleMeshShape,
    BulletWorld,
)
from panda3d.core import BitMask32, TransformState, Vec3

from coastal_map import SEA_LEVEL, map_meshes, on_road
from highway_driver import HighwayDriver
from highway_map import HIGHWAY_LENGTH, collision_boxes, traffic_spawns
from highway_map import SPAWN as HIGHWAY_SPAWN
from highway_map import on_road as highway_on_road
from highway_segments import REBASE_DISTANCE, SEGMENT_LENGTH
from streamed_road import StreamedRoad
from test_track import OBSTACLES, SPAWN, on_asphalt
from traffic import Driver, Road, extents
from traffic_recovery import TrafficRecovery
from vehicle import Vehicle
from vehicle_state import FIXED_DT, CarState, Control, WheelState, forward, heading_for
from world_props import collision_box, props_for

__all__ = [
    "FIXED_DT",
    "CarState",
    "Control",
    "Simulation",
    "Snapshot",
    "WheelState",
    "forward",
    "heading_for",
    "interpolate",
]


@dataclass(frozen=True)
class Snapshot:
    tick: int
    time: float
    player: CarState
    traffic: tuple[CarState, ...]
    events: tuple[str, ...] = ()
    origin_y: float = 0.0
    collisions: int = 0


class Simulation:
    def __init__(self, seed=0, *, track="coastal", wind=(0, 0, 0), traffic_count=None,
                 road_shape="straight", traffic_span=540):
        self.wind = Vec3(*wind)
        self.track = track
        self.road_shape = road_shape
        self.traffic_span = traffic_span
        self.traffic_count = (
            (12 if track == "endless" else 8 if track == "highway" else 0)
            if traffic_count is None
            else traffic_count
        )
        self.road = Road(track)
        self.on_asphalt = {
            "coastal": on_road,
            "highway": highway_on_road,
            "test": on_asphalt,
            "endless": lambda x, y: abs(x) <= 6.75,
        }[track]
        self.spawn = HIGHWAY_SPAWN if track in ("highway", "endless") else SPAWN
        self.closed = False
        self._world = None
        self.player = None
        self.npcs = []
        self.reset(seed)

    @property
    def response(self):
        return self.player.response

    def reset(self, seed=0):
        if self.closed:
            raise RuntimeError("Simulation is closed")
        self._destroy_physics()
        self.seed = seed
        self.origin_y = 0.0
        self.road = Road(self.track, seed=seed, shape=self.road_shape)
        if self.track == "endless" and not self.road.curve:
            self.on_asphalt = lambda x, y: abs(x) <= 6.75
            self.spawn = HIGHWAY_SPAWN
        if self.road.curve:
            self.on_asphalt = lambda x, y: self.road.curve.on_asphalt(x, y + self.origin_y)
            p = self.road.sample(8, 1)
            self.spawn = (p.x, p.y, p.z + 0.55)
        self.rebases = 0
        self.stream = None
        self._tick = 0
        self._events = ()
        self.npcs = []
        self.drivers = []
        self._traffic_bodies = []
        self._traffic = []
        self._traffic_controls = []
        self._retired_traffic = set()
        self._generations = []
        self.traffic_cycles = 0
        self._prop_bodies = []
        self.collision_count = 0
        self.player_collisions = 0
        self._last_contact_tick = -120
        self.props = []
        self._build_world()
        self._build_traffic()

    def set_checkpoint_frames_enabled(self, enabled):
        # Hidden frames must not remain under wheel rays or ground-height queries.
        for body in self._prop_bodies:
            if body.getName().startswith("checkpoint"):
                body.setIntoCollideMask(BitMask32(3) if enabled else BitMask32.allOff())

    def _build_world(self):
        self._world = BulletWorld()
        self._world.setGravity(Vec3(0, 0, -9.81))

        if self.track == "coastal":
            self._build_road(map_meshes())
        elif self.track == "endless":
            self.stream = StreamedRoad(self._world, self.seed, self.road.curve)
            self.stream.update(8, self.origin_y, [])
        elif self.track == "highway":
            for name, (half, center) in collision_boxes().items():
                # Short boxes keep Bullet's wheel rays accurate along this long road.
                count = math.ceil(half[1] * 2 / 40)
                length = half[1] * 2 / count
                for index in range(count):
                    body = BulletRigidBodyNode(name)
                    if "rail" in name:
                        shape = BulletBoxShape(Vec3(half[0], length / 2, half[2]))
                    else:
                        # Triangle rays avoid the convex solver's false heights near slab ends.
                        mesh = BulletTriangleMesh()
                        a = Vec3(-half[0], -length / 2, half[2])
                        b = Vec3(half[0], -length / 2, half[2])
                        c = Vec3(half[0], length / 2, half[2])
                        d = Vec3(-half[0], length / 2, half[2])
                        mesh.addTriangle(a, b, c)
                        mesh.addTriangle(a, c, d)
                        shape = BulletTriangleMeshShape(mesh, dynamic=False)
                        shape.setMargin(0.01)
                    body.addShape(shape)
                    y = center[1] - half[1] + (index + 0.5) * length
                    body.setTransform(TransformState.makePos(Vec3(center[0], y, center[2])))
                    body.setIntoCollideMask(BitMask32(7))
                    self._world.attachRigidBody(body)
        else:
            ground = BulletRigidBodyNode("test-ground")
            ground.addShape(BulletPlaneShape(Vec3(0, 0, 1), 0))
            self._world.attachRigidBody(ground)
            for obstacle in OBSTACLES:
                body = BulletRigidBodyNode(obstacle.name)
                body.addShape(BulletBoxShape(Vec3(*obstacle.half_size)))
                body.setTransform(
                    TransformState.makePosHpr(Vec3(*obstacle.center), Vec3(0, obstacle.pitch, 0))
                )
                self._world.attachRigidBody(body)

        self._build_props()
        self.player = Vehicle(self._world, self.on_asphalt, self.spawn, wind=self.wind)
        if self.road.curve:
            p = self.road.sample(8, 1)
            self.player.reset(self.spawn, p.heading, p.grade)
        self._chassis = self.player._chassis
        self._vehicle = self.player._vehicle

    def _build_road(self, meshes):
        for name, (vertices, triangles) in meshes.items():
            mesh = BulletTriangleMesh()
            for triangle in triangles:
                mesh.addTriangle(*(Vec3(*vertices[i]) for i in triangle))
            shape = BulletTriangleMeshShape(mesh, dynamic=False)
            shape.setMargin(0.01)
            body = BulletRigidBodyNode(name)
            body.addShape(shape)
            # Bits 0/1/2 are surface queries, vehicle collision and camera obstruction.
            body.setIntoCollideMask(BitMask32(7))
            self._world.attachRigidBody(body)

    def _build_props(self):
        for index, prop in enumerate(props_for(self.track)):
            z = self.ground_height(prop.x, prop.y)
            if prop.kind in ("tree", "rock"):
                z += 0.05 * prop.scale
            half, height = collision_box(prop)
            center = Vec3(prop.x, prop.y, z + height)
            body = BulletRigidBodyNode(f"{prop.kind}-{index}")
            body.addShape(BulletBoxShape(Vec3(*half)))
            body.setTransform(TransformState.makePosHpr(center, Vec3(prop.heading, 0, 0)))
            # Frames collide with cars but do not pull the chase camera forward.
            body.setIntoCollideMask(BitMask32(3 if prop.kind.startswith("checkpoint") else 7))
            self._world.attachRigidBody(body)
            self.props.append((prop, z))
            self._prop_bodies.append(body)

    def _build_traffic(self):
        rng = random.Random(self.seed)
        spawns = traffic_spawns(self.seed)
        for i in range(self.traffic_count):
            if self.track in ("highway", "endless"):
                initial = spawns[i % len(spawns)]
                lane, distance, speed = (
                    initial.lane,
                    90 + i * (self.traffic_span if self.track == "endless" else 1200) / self.traffic_count,
                    initial.speed,
                )
            else:
                lane, distance, speed = (
                    i % 2,
                    (i + 1) * self.road.length / (self.traffic_count + 1),
                    rng.uniform(12, 17),
                )
            p = self.road.sample(distance, lane)
            car = Vehicle(
                self._world,
                self.on_asphalt,
                (p.x, p.y, p.z + 0.55),
                name=f"traffic-{i}",
                wind=self.wind,
                heading=p.heading,
                pitch=p.grade,
                reverse_enabled=False,
            )
            self.npcs.append(car)
            self.drivers.append(Driver(lane, speed))
            if self.track == "endless":
                self.drivers[-1] = HighwayDriver(lane, self.seed * 1009 + i * 9176 + 41)
            self._traffic_bodies.append(car._chassis)
            self._traffic.append([lane, distance, speed])
            self._traffic_controls.append(Control())
            self._generations.append(0)

    def _drive_traffic(self):
        states = [self.player.snapshot(), *[n.snapshot() for n in self.npcs]]
        locations = [self.road.locate(state) for state in states]
        lane_states = (
            [self.road.lane_frame(state, p) for state, p in zip(states, locations)]
            if self.road.curve else None
        )
        reservations = {
            i: (d.target_lane, locations[i + 1][0], states[i + 1].speed)
            for i, d in enumerate(self.drivers)
            if isinstance(d, HighwayDriver)
            and d.phase in ("signal", "changing")
            and self.npcs[i]._chassis not in self._retired_traffic
        }
        for i, (car, driver) in enumerate(zip(self.npcs, self.drivers)):
            if car._chassis in self._retired_traffic:
                continue
            neighbors = [
                j for j in range(len(states))
                if j != i + 1 and (j == 0 or self.npcs[j - 1]._chassis not in self._retired_traffic)
            ]
            others = [states[j] for j in neighbors]
            positions = [locations[i + 1], *[locations[j] for j in neighbors]]
            if isinstance(driver, HighwayDriver):
                sensed = (
                    [lane_states[i + 1], *[lane_states[j] for j in neighbors]]
                    if lane_states is not None else None
                )
                occupied = [value for key, value in reservations.items() if key != i]
                driver.plan(states[i + 1], others, self.road, occupied, lane_states=sensed)
                if driver.phase in ("signal", "changing"):
                    reservations[i] = (
                        driver.target_lane,
                        locations[i + 1][0],
                        states[i + 1].speed,
                    )
                else:
                    reservations.pop(i, None)
                self._traffic_controls[i] = driver.control(
                    states[i + 1], others, self.road, positions, lane_states=sensed
                )
            else:
                self._traffic_controls[i] = driver.control(
                    states[i + 1], others, self.road, positions
                )

    def _position_clear(self, point, heading, *, ignore=None, speed=0):
        candidate = CarState(tuple(point), heading, speed)
        distance, lateral = self.road.locate(candidate)
        road_heading = self.road.sample(distance, 0).heading
        width, length = extents(heading, road_heading)
        for car in [self.player, *self.npcs]:
            if car is ignore or car._chassis in self._retired_traffic:
                continue
            state = car.snapshot()
            other_s, other_lateral = self.road.locate(state)
            other_width, other_length = extents(state.heading, road_heading)
            if abs(other_lateral - lateral) > width + other_width + 0.4:
                continue
            delta = self.road.delta(other_s, distance)
            gap = abs(delta) - length - other_length
            # Require the approaching car's stopping distance as well as empty space.
            other_speed = state.speed * math.cos(math.radians(state.heading - road_heading))
            closing = max(0, (other_speed - speed) if delta < 0 else (speed - other_speed))
            if gap < 3 + closing * 0.5 + closing**2 / 8:
                return False
        return True

    def _outside_player_view(self, position):
        player = self.player.snapshot()
        delta = Vec3(*position) - Vec3(*player.position)
        distance = delta.length()
        # Beyond the fog, or well behind the broad chase-camera view.
        return distance > 900 or (
            distance > 160 and delta.dot(forward(player.heading)) < -0.3 * distance
        )

    def _recycle_traffic(self):
        if self.track != "highway":
            return
        for i, car in enumerate(self.npcs):
            body = car._chassis
            if (
                body not in self._retired_traffic
                and body.getTransform().getPos().y < HIGHWAY_LENGTH - 15
            ):
                continue
            if body not in self._retired_traffic:
                if not self._outside_player_view(body.getTransform().getPos()):
                    continue
                self._world.removeVehicle(car._vehicle)
                self._retired_traffic.add(body)
                self._generations[i] += 1
            lane = self.drivers[i].lane
            for distance in range(30, 1250, 40):
                p = self.road.sample(distance, lane)
                position = (p.x, p.y, p.z + 0.55)
                if not self._outside_player_view(position):
                    continue
                if not self._position_clear(position, p.heading, ignore=car):
                    continue
                car.reset(position, p.heading, p.grade)
                self._world.attachRigidBody(body)
                self._world.attachVehicle(car._vehicle)
                self._retired_traffic.remove(body)
                self.drivers[i].recovering = False
                self._traffic_controls[i] = Control()
                self._generations[i] += 1
                self.traffic_cycles += 1
                self._events += (f"traffic_recycled:{i}",)
                break

    def _update_stream(self):
        player_y = self.road.locate(self.player.snapshot())[0]
        for i, car in enumerate(self.npcs):
            body = car._chassis
            if body not in self._retired_traffic:
                if abs(self.road.locate(car.snapshot())[0] - player_y) < 1100:
                    continue
                self._world.removeVehicle(car._vehicle)
                self._retired_traffic.add(body)
                self._generations[i] += 1
            # Alternate front and rear entries; no visible car is moved.
            direction = 1 if (i + self._generations[i] // 2) % 2 else -1
            lane = self.drivers[i].lane
            for offset in (960, 1000, 1040):
                p = self.road.sample(player_y + direction * offset, lane)
                point = (p.x, p.y, p.z + 0.55)
                if not self._position_clear(point, p.heading, ignore=car):
                    continue
                car.reset(point, p.heading, p.grade)
                self._world.attachRigidBody(body)
                self._world.attachVehicle(car._vehicle)
                self._retired_traffic.remove(body)
                self.drivers[i].recovering = False
                self.drivers[i].cancel()
                self.drivers[i].recovery = TrafficRecovery()
                self.drivers[i].recovery_action = None
                self._traffic_controls[i] = Control()
                self._generations[i] += 1
                self.traffic_cycles += 1
                self._events += (f"traffic_recycled:{i}",)
                break
        occupied = [
            self.road.locate(car.snapshot())[0] + (0 if self.road.curve else self.origin_y)
            for car in [self.player, *self.npcs]
            if car._chassis not in self._retired_traffic
        ]
        self.stream.update(player_y + (0 if self.road.curve else self.origin_y), self.origin_y, occupied)

    def _rebase(self):
        local_y = self.player.snapshot().position[1]
        if abs(local_y) < REBASE_DISTANCE:
            return
        amount = math.trunc(local_y / SEGMENT_LENGTH) * SEGMENT_LENGTH
        for car in [self.player, *self.npcs]:
            car.shift(amount)
        if not self.road.curve:
            for driver in self.drivers:
                driver.start_y -= amount
        self.stream.shift(amount)
        self.origin_y += amount
        self.road.origin_y = self.origin_y
        self.rebases += 1
        self._events += ("origin_shift",)

    def recover_player(self):
        if self.track == "test":
            self.reset_player()
            return True
        state = self.player.snapshot()
        distance, lateral = self.road.locate(state)
        lanes = sorted(range(len(self.road.lanes)), key=lambda i: abs(self.road.lanes[i] - lateral))
        for offset in (0, -8, 8, -16, 16, -30, 30):
            target_s = distance + offset
            if not self.road.closed and not self.road.endless:
                target_s = max(8, min(HIGHWAY_LENGTH - 10, target_s))
            for lane in lanes:
                p = self.road.sample(target_s, lane)
                position = (p.x, p.y, p.z + 0.55)
                if self._position_clear(position, p.heading, ignore=self.player):
                    self.reset_player(position, p.heading, p.grade)
                    return True
        self._events = ("reset_blocked",)
        return False

    def reset_player(self, position=None, heading=None, pitch=0):
        if self.closed:
            raise RuntimeError("Simulation is closed")
        at_spawn = position is None
        if at_spawn and self.stream:
            distance = 8 if self.road.curve else 8 - self.origin_y
            p = self.road.sample(distance, 1)
            position = (p.x, p.y, p.z + 0.55)
            heading = p.heading if heading is None else heading
            pitch = p.grade
        self.player.reset(
            self.spawn if position is None else position, 0 if heading is None else heading, pitch
        )
        if at_spawn and self.stream:
            self._update_stream()
        self._events = ("player_reset",)

    def _destroy_physics(self):
        if self._world is not None:
            for car in [self.player, *self.npcs]:
                if car._chassis not in self._retired_traffic:
                    car.close()
            self._world = None
        self.player = None
        self._chassis = self._vehicle = None

    def step(self, control: Control, dt=FIXED_DT):
        if self.closed:
            raise RuntimeError("Simulation is closed")
        if not math.isclose(dt, FIXED_DT, rel_tol=0, abs_tol=1e-12):
            raise ValueError("Simulation requires a 1/120 second step")
        self._events = ()
        if self._tick % 6 == 0:
            if self.stream:
                self._update_stream()
            self._recycle_traffic()
            self._drive_traffic()
        cars = [
            (self.player, control),
            *[
                (car, action)
                for car, action in zip(self.npcs, self._traffic_controls)
                if car._chassis not in self._retired_traffic
            ],
        ]
        velocities = [Vec3(car._chassis.getLinearVelocity()) for car, _ in cars]
        for car, action in cars:
            car.apply_control(action)
        self._world.doPhysics(FIXED_DT, 4, FIXED_DT)
        for (car, _), velocity in zip(cars, velocities):
            car.after_step(velocity)
        self.collision_count += sum(
            self._world.contactTestPair(self._chassis, body).getNumContacts() > 0
            for body in self._traffic_bodies
            if body not in self._retired_traffic
        )
        self._count_player_collisions()
        self._tick += 1
        if self.stream:
            self._rebase()
        if self._chassis.getTransform().getPos().z < SEA_LEVEL - 1:
            self.recover_player()
        if self._tick % 120 == 0:
            # Headless runs have no render loop to collect Panda's cached transforms.
            TransformState.garbageCollect()

    def _count_player_collisions(self):
        # Count an impact episode, not every physics step spent rubbing a barrier.
        for contact in self._world.contactTest(self._chassis).getContacts():
            other = contact.getNode1() if contact.getNode0() == self._chassis else contact.getNode0()
            name = other.getName()
            if not any(kind in name for kind in ("traffic", "rail", "tree", "rock", "checkpoint", "wall")):
                continue
            if contact.getManifoldPoint().getDistance() > 0:
                continue
            if self._tick - self._last_contact_tick >= 120:
                self.player_collisions += 1
                self._events += ("player_collision",)
            self._last_contact_tick = self._tick
            break

    def snapshot(self):
        traffic = tuple(
            replace(
                car.snapshot(),
                active=car._chassis not in self._retired_traffic,
                generation=self._generations[i],
                signal=self.drivers[i].signal if isinstance(self.drivers[i], HighwayDriver) else 0,
                hazards=self.drivers[i].recovering,
            )
            for i, car in enumerate(self.npcs)
        )
        return Snapshot(
            self._tick,
            self._tick * FIXED_DT,
            self.player.snapshot(),
            traffic,
            self._events,
            self.origin_y,
            self.player_collisions,
        )

    def close(self):
        if self.closed:
            return
        self._destroy_physics()
        self.npcs.clear()
        self._traffic.clear()
        self.closed = True

    def camera_position(self, anchor, desired):
        """Keep a camera-sized sphere clear of scenery, without advancing the world."""
        anchor, desired = Vec3(*anchor), Vec3(*desired)
        hit = self._world.sweepTestClosest(
            BulletSphereShape(0.3),
            TransformState.makePos(anchor),
            TransformState.makePos(desired),
            BitMask32.bit(2),
        )
        if hit.hasHit():
            return anchor + (desired - anchor) * max(0, hit.getHitFraction() - 0.025)
        return desired

    def ground_height(self, x, y):
        hit = self._world.rayTestClosest(Vec3(x, y, 50), Vec3(x, y, -30), BitMask32.bit(0))
        return hit.getHitPos().z if hit.hasHit() else SEA_LEVEL


def interpolate(previous: Snapshot, current: Snapshot, alpha: float):
    if previous.origin_y != current.origin_y:
        previous = shift_snapshot(previous, current.origin_y)

    def angle(a, b):
        return a + ((b - a + 180) % 360 - 180) * alpha

    def vector(a, b):
        return tuple(x + (y - x) * alpha for x, y in zip(a, b))

    def orientation(a, b):
        sign = 1 if sum(x * y for x, y in zip(a, b)) >= 0 else -1
        value = vector(a, tuple(sign * x for x in b))
        length = math.sqrt(sum(x * x for x in value))
        return tuple(x / length for x in value)

    def car(a, b):
        if a.generation != b.generation or a.active != b.active:
            return b
        return CarState(
            vector(a.position, b.position),
            angle(a.heading, b.heading),
            a.speed + (b.speed - a.speed) * alpha,
            angle(a.pitch, b.pitch),
            angle(a.roll, b.roll),
            tuple(
                WheelState(
                    vector(x.position, y.position), orientation(x.orientation, y.orientation)
                )
                for x, y in zip(a.wheels, b.wheels)
            ),
            b.surface,
            a.steering + (b.steering - a.steering) * alpha,
            a.throttle + (b.throttle - a.throttle) * alpha,
            a.brake + (b.brake - a.brake) * alpha,
            a.rpm + (b.rpm - a.rpm) * alpha,
            b.gear,
            a.acceleration + (b.acceleration - a.acceleration) * alpha,
            a.lateral_acceleration + (b.lateral_acceleration - a.lateral_acceleration) * alpha,
            b.dynamics,
            b.active,
            b.generation,
            b.signal,
            vector(a.velocity, b.velocity) if a.velocity and b.velocity else b.velocity,
            b.hazards,
        )

    return replace(
        current,
        player=car(previous.player, current.player),
        traffic=tuple(car(a, b) for a, b in zip(previous.traffic, current.traffic)),
    )


def shift_snapshot(state, origin):
    offset = state.origin_y - origin

    def shift(car):
        x, y, z = car.position
        return replace(
            car,
            position=(x, y + offset, z),
            wheels=tuple(
                replace(w, position=(w.position[0], w.position[1] + offset, w.position[2]))
                for w in car.wheels
            ),
        )

    return replace(
        state, player=shift(state.player), traffic=tuple(map(shift, state.traffic)), origin_y=origin
    )
