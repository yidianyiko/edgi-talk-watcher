# Project verification

Current intent and boundaries: `CONTEXT.md`. Board status transport, flash offsets and recovery: `docs/board-status.md`.

## Commands

- Host tests: `python3 -m unittest discover -s tests -p 'test_*.py'`
- Browser session logic: `node --test tests/watcher_state.test.mjs`
- Board protocol test and M55 build: `bash tools/build_board_status.sh`
- Real board automatic status test (Windows/WSL): `powershell.exe -NoProfile -File "$(wslpath -w tools/board_status.ps1)" -SelfTest`
- One billable real model decision to board: `python3 -m tools.judge_to_board <one-case-manifest.json> --hold-seconds 10`
- Bounded physical-camera continuous test (billable): `python3 -m tools.continuous_watch --task '<task>' --seconds 300 --interval 5 --max-calls 60`
- Windows file publication regression: run `tests/test_camera_publication_windows.py` with the installed Windows Python; Linux skips its sharing-semantics test.

- Hippo enclosure STL export: `QT_QPA_PLATFORM=offscreen python3 design/enclosure/hippo-v1/export.py`
- Hippo enclosure geometry checks (Python with numpy/trimesh): `python3 design/enclosure/hippo-v1/verify_meshes.py` and `QT_QPA_PLATFORM=offscreen python3 design/enclosure/hippo-v1/check_clearances.py`; fit limits and setup: `design/enclosure/hippo-v1/README.zh.md`.
