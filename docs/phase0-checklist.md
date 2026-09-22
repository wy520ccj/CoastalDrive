# Phase 0 checklist

## Scope

Prepare the Windows Python development environment, runtime asset layout, licensing register, and a minimal Panda3D/Bullet/GLB/audio/Chinese text/packaging smoke test. Do not modify the legacy ADAS project.

## Baseline

- [x] Legacy source and archive were inspected.
- [x] Baseline hashes were saved in `legacy-baseline-sha256.txt`.
- [x] New project directory is separate from `ADAS`.

## Environment

- [x] Python 3.14 selected after the available 3.12 executable failed to start due to a missing runtime DLL.
- [x] Python 3.14 virtual environment created.
- [x] Runtime dependencies installed from `requirements.txt`.
- [x] Development tools installed from `requirements-dev.txt` entries.
- [x] PyCharm was launched with the project path; the project interpreter is ready at `.venv\\Scripts\\python.exe`.
- [x] Steam Blender import/export path verified with a background GLB round trip.

## Assets

- [x] Kenney Car Kit, Racing Kit and Nature Kit downloaded into `assets/raw/`.
- [x] Kenney package licenses and selected contents recorded.
- [x] The original GLB and the Blender round-trip GLB load in Panda3D.
- [x] Player and traffic GLB files are placed in `assets/game/`.

## Smoke tests

- [x] Panda3D offscreen OpenGL window opens and closes.
- [x] OpenGL renderer is recorded; the system reports an NVIDIA GPU.
- [x] Bullet world steps a rigid body.
- [x] A GLB model and its shared texture load.
- [x] Chinese text is accepted by the runtime text object.
- [x] A generated WAV loads without an audio-device crash.
- [x] The Windows x64 smoke application is packaged with `build_apps` and launched.

## Evidence

Environment, Blender, and smoke-test reports are stored under `logs/` and `docs`. If PyCharm does not select the project interpreter automatically, choose `CoastalDrive\\.venv\\Scripts\\python.exe` once in the project interpreter settings.
