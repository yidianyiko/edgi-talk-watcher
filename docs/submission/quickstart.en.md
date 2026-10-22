# Watcher: technical quick start

Watcher monitors a single visual target appearing or disappearing. A Chinese instruction becomes a validated task; sampled camera images are compared by the existing Jev model. New events retain before/after images and update the Edgi Talk display. This is a board plus host prototype: ASR, task compilation, inference access and persistent history use the host. No target-specific model is trained.

## Requirements

- Infineon Edgi Talk (PSoC Edge E84) with the project firmware; retain the existing M33 image.
- UVC camera on the board USB host for board-camera testing. V8 has verified 320×240 YUYV capture (153600 bytes per frame).
- The existing Windows/WSL environment, KitProg3 UART, RT-Thread toolchain and Windows Python used by the project helpers.
- Board and Windows host on a reachable trusted Wi-Fi LAN. The upload transport is authenticated HTTP, without TLS.
- Existing Jev access and an installed, authenticated Codex CLI (`codex exec`), which compiles new Chinese tasks into validated plans. The CLI must be available on PATH; cached plans can be reused. New visual decisions can incur API charges.

Keep credentials in private `.env.local`, never in an article, archive or command transcript:

```dotenv
JEV_TOKEN=<private-value>
WIFI_SSID=<your-network>
WIFI_PASSWORD=<private-value>
```

## Local environment

```sh
uv venv --system-site-packages .venv
uv pip install --python .venv/bin/python -r requirements.txt -r requirements-voice.txt
.venv/bin/python -m tools.setup_local_asr
```

The ASR installer verifies pinned model files. Runtime ASR uses local Whisper base; visual decisions use Jev `jev-1.14.0`, confidence threshold 0.8. The screen currently uses ASCII; the web page shows the full Chinese transcript.

## Windows path adaptation before voice launch

The current board voice launcher was verified on the author's Windows/WSL workstation. `tools/run_product.py` currently hardcodes the Windows Python executable in `prepare_voice_proxy`; replace that path with the WSL-mounted path of your installed Windows Python before using `--voice`. It has no launcher flag for overriding that path. `tools/voice_capture.py`, `tools/pc_camera_relay.py` and `tools/continuous_watch.py` also contain workstation-specific fallback paths; review those if using their camera modes. Host-only web mode does not use this Windows proxy path. This source snapshot is not a portable one-command installer.

## Running and operation

The current launcher defaults to the board USB camera in voice mode. Check `tools.run_product --help` and `docs/board-voice.md` for current options. Run:

```sh
.venv/bin/python -m tools.run_product --voice --seconds 86400
```

Open http://localhost:8765/ for tasks, transcript and event history. The launcher configures board Wi-Fi, a scoped Windows LAN upload proxy, and the UART bridge. Its gateway token is generated in the private data directory. The initial state is paused.

Use SPEAK for a six-second recording, then say a task such as “当画面中原本可见的手消失时提醒我”, “暂停看守”, or “继续看守”. The physical touch interaction is implemented; further physical testing was explicitly waived by the user on 2026-10-22. Existing automated hardware checks invoke the same recording entry via UART and play saved speech through the computer speaker.

A board-camera session is bounded to 300 seconds / 60 uploads: one reference and at most 59 model comparisons. Uncertain results are not treated as “nothing happened”. Errors pause the watch. A paused or replaced session must not accept late decisions. Event history is local SQLite, capped at 100 events, with deletable before/after evidence. Restart defaults to paused.

Use `--camera-source pc` for the explicit PC-camera fallback. The current source and flashed V10 firmware integrate voice commands, the board camera and newly committed event announcements. Follow [the current integration report](../board-camera-integration.md) for actual acceptance results. V9 reached seven starts but failed during final shutdown; that run did not pass. V10 has been built, reviewed and flash-verified. The corrected build passed seven starts/stops with model-error and relay-loss recovery, a 300-second-budget sampled-camera soak, and three saved-PCM start/pause cycles through the actual default launcher. Recovery included one real Jev comparison; the other acceptance visual decisions were controlled. See the report for timings and preserved failed V9 evidence. At the historical V8 checkpoint shown in the demo, the daily launcher still used the PC camera. The video therefore does not demonstrate the current integrated runtime.

## Reproduce a model result without new camera work or API calls

The following command requires separately retained private fixtures: `testdata/` recordings and `artifacts/` response logs are excluded from the public source snapshot. With those files available, the hand-removal recording and task-bound model responses replay through the shared state machine:

```sh
.venv/bin/python -m tools.replay_session testdata/recordings/hand-removal \
  --plan testdata/plans/hand-disappears.json \
  --responses artifacts/product-completion/recorded/hand-removal/responses-bound.jsonl \
  --output artifacts/submission/offline-replay
```

Expected: end-of-recording completion, one alert, nine replayed decisions and zero live model calls. This replays saved responses; it is not a new accuracy evaluation. The source recording contains sparse timestamped JPEG frames; its MP4 is a reconstruction.

## Verification and firmware precautions

```sh
.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
node --test tests/watcher_state.test.mjs
bash tools/build_board_status.sh
bash tools/build_board_voice.sh
```

On a clean BSP, run the status build first to generate the base project, then the voice build. Run vendor SCons builds serially because they share generated objects. See `source-build-notes.en.md` for the source archive and pinned BSP requirements. See `docs/board-status.md` for backup, flash offsets and recovery. Building does not flash. Verify the actual image size against the M55 slot and read back/verify after flashing; do not copy flash commands without checking the current image and board state.

## Evidence limits

The V8 board uploaded two real camera frames over Wi-Fi, with one real Jev result (`uncertain`, no event). The archived PC-camera evaluation made 67 real decisions over three recordings and saved two events. Neither is a 24-hour hardware reliability study or a general accuracy benchmark. Hardware PLAY/DONE responses establish playback control flow; audible volume and clarity lack independent acoustic evidence, and the user has waived further physical testing. The source video contains no synthesized board sound to mask that gap.
