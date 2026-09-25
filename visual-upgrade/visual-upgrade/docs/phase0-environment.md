# Phase 0 environment report

Date: 2026-09-20

## Selected environment

- OS target: Windows x64
- IDE: `B:\AI agent\py\PyCharm 2025.1.6.1\bin\pycharm64.exe`
- Runtime: Python 3.14.2 at `C:\Users\15120\AppData\Local\Python\pythoncore-3.14-64\python.exe`
- Project interpreter: `B:\AI agent\暑期计算机程序设计\CoastalDrive\.venv\Scripts\python.exe`
- Renderer reported by Panda3D: OpenGL
- Hardware available during inspection: RTX 4060 Laptop GPU, i9-13900HX, about 16 GB RAM

The machine also contains `B:\python.exe`, labelled Python 3.12.6. It exits with Windows loader error `-1073741515` because its required runtime DLL is unavailable. It is not used by this project. Python 3.14 was selected because it runs normally and Panda3D 1.10.16 provides a matching Windows wheel.

## Installed runtime

- Panda3D 1.10.16
- panda3d-simplepbr 0.13.1
- panda3d-gltf 1.3.0
- pytest 8.4.2
- ruff 0.16.8

The runtime requirements are in `requirements.txt`; development requirements are in `requirements-dev.txt`; the local environment lock is in `requirements-lock.txt`.

## Asset preparation

Downloaded and expanded for inspection:

- Kenney Car Kit 3.1, CC0
- Kenney Racing Kit 2.0, CC0
- Kenney Nature Kit 2.1, CC0

The runtime asset folder currently contains the player sports sedan, a traffic sedan, and the shared `colormap.png` texture. The texture was copied after the first GLB test showed that a model-only copy was incomplete.

## Smoke-test result

`tools/phase0_smoke.py` passed all required checks:

- Panda3D offscreen OpenGL window
- simplepbr import
- Bullet gravity step
- GLB model and texture loading
- Chinese text object creation
- generated WAV loading

The JSON evidence is in `logs/phase0-smoke.json`.

## Packaging result

`setup.py build_apps` completed successfully for `win_amd64`. The packaged executable is:

`build/win_amd64/coastaldrive-phase0.exe`

It was launched from the packaged folder and remained running for four seconds before being stopped by the validation command. The package includes the player and traffic models and the shared texture.

Panda3D emitted a non-fatal packaging warning that `api-ms-win-core-path-l1-1-0.dll` was not found while assembling the embedded Python runtime. The resulting executable launched successfully on this machine; the warning should be rechecked when a release package is tested on a clean machine.

## Blender and PyCharm

- Steam Blender executable: `B:\\steam\\steamapps\\common\\Blender\\blender.exe`
- Blender version: 5.2.2 LTS
- Background import/export check: passed. The source vehicle contained 6 objects, 6 meshes, and 1 material; the exported GLB was 131,880 bytes.
- Panda3D loaded the Blender round-trip GLB in the phase 0 smoke test. Evidence is in `logs/phase0-blender.json` and `logs/phase0-smoke.json`.
- PyCharm 2025.1.6.1 was launched with the `CoastalDrive` project path. The project interpreter is ready at `CoastalDrive\\.venv\\Scripts\\python.exe`.
- If PyCharm does not auto-select it, choose that interpreter once in Settings > Project > Python Interpreter.
