# Phase 2 H1 vehicle physics

> Historical phase-2 implementation report. The initial 31 checks missed a sleeping vehicle that could not restart, incorrect steering, and unreliable wheel contact. This report is superseded by [H1-review.md](H1-review.md); the initial integration was not sufficient to pass H1.

## Scope

H1 replaces the phase 1 kinematic player motion inside `Simulation` with a Panda3D Bullet vehicle. The public simulation boundary stays unchanged: `Control`, `reset`, `reset_player`, `step`, `snapshot`, `close`, fixed `1/120` seconds, and immutable snapshot values remain the interfaces used by the session and display layers.

## Implementation

- `BulletWorld` contains a large static test ground and one four-wheel `BulletVehicle`.
- The chassis uses a box collision shape, mass, damping, four suspension wheels, friction, and roll influence.
- Steering, engine force, braking, and the existing 0.4 second brake-to-reverse rule are applied inside `Simulation`.
- Traffic remains the deterministic prototype stream until a separate traffic physics gate is defined.
- `scene.py` still consumes only `Snapshot` values; it does not own Bullet objects or advance physics.
- The world is rebuilt on session reset and removed on close so repeated restarts do not accumulate physics objects.

## Validation

- `pytest -q`: 31 tests passed, including Bullet wheel count, ground settling, reset pose, fixed-step, input, pause, and lifecycle checks.
- `ruff check src tests tools`: passed.
- `src/main.py --headless --steps 10000 --seed 17`: completed at tick 10,000 with the chassis still above the test ground.
- Offscreen and real-window smoke runs: passed on the NVIDIA RTX 4060 renderer; screenshots and restart stability reports were generated under `logs/h1-ui/` and `logs/h1-window/`.

## Boundary

This is a vehicle-physics gate, not a final handling or visual acceptance. The current car still has a box chassis, simple wheel setup, a flat test field, no body damage, no tire model, and no race rules. The next H1 tuning work should measure braking, steering response, stability, and control observations before formal map or AI work resumes.
