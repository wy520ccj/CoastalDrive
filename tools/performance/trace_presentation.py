"""只记录真实发布、显示位置与相机；不改变控制、插值或物理步。"""
import hashlib
import json
import os
import pickle
import sys
import time
from dataclasses import replace
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[2]
    source = Path(sys.argv[sys.argv.index('--source') + 1]) if '--source' in sys.argv else root / 'src'
    sys.path.insert(0, str(source.resolve()))
    sys.path.insert(0, str(root / 'tools' / 'performance'))
    import paths
    paths.resource_root = lambda: root
    import benchmark_runtime

    from application import CoastalDrive
    from session_clock import SessionClock

    published, rendered, hashes = [], [], []
    original_publish = SessionClock.publish
    original_apply = CoastalDrive.apply_scene
    original_camera = __import__('session').Session.camera_position
    camera_queries = []

    def positions(state):
        return [tuple(car.position) for car in (state.player, *state.traffic)]

    def publish(clock):
        original_publish(clock)
        published.append((time.perf_counter(), clock.current.tick,
                          clock.current.origin_y, positions(clock.current)))
        if os.environ.get('PHYS_STRUCT_HASH') and (not hashes or hashes[-1][0] != clock.current.tick):
            state = replace(clock.current, contact_epoch=0, impacts=tuple(replace(e, epoch=0) for e in clock.current.impacts))
            hashes.append((state.tick, hashlib.sha256(pickle.dumps(state, protocol=5)).hexdigest()))

    def camera(session, *arguments):
        started = time.perf_counter()
        result = original_camera(session, *arguments)
        camera_queries.append((time.perf_counter() - started) * 1000)
        return result

    def apply(app, state, dt):
        started = time.perf_counter()
        original_apply(app, state, dt)
        rendered.append((started, state.tick, state.origin_y, positions(state),
                         tuple(app.camera.getPos()), dt,
                         (time.perf_counter() - started) * 1000))

    SessionClock.publish = publish
    CoastalDrive.apply_scene = apply
    __import__('session').Session.camera_position = camera
    try:
        return benchmark_runtime.main()
    finally:
        output = Path(sys.argv[sys.argv.index('--output') + 1])
        (output / 'presentation.json').write_text(json.dumps({
            'published': published, 'rendered': rendered,
            'camera_query_ms': camera_queries,
        }), encoding='utf-8')
        if hashes:
            (output/'clock-hashes.json').write_text(json.dumps(hashes), encoding='utf-8')


if __name__ == '__main__':
    raise SystemExit(main())
