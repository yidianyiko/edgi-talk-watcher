# Board-camera daily workflow

Approved scope: finish tasks 1–4 from the current project conversation. The user moved the UVC camera onto Edgi Talk and requested autonomous completion using retained test material.

1. The normal `tools.run_product --voice` workflow uses the board USB camera. Preserve explicit `--camera-source pc` and archived recording regression modes. The Windows relay admits only authenticated board voice/camera uploads; UI stays local.
2. A successful voice start means an actual first board frame reached the shared gateway. One serial bridge owns task/status, capture lifecycle and announcements. Pause, task changes and superseding owners invalidate delayed uploads/results. Sessions remain bounded to 300 seconds and 60 uploads (at most 59 model comparisons).
3. Newly committed board-camera events use the existing announcement FIFO exactly once. Preserve received valid frames, including failed model requests, for offline debugging. Test nominal start/stop, repeat sessions, transport/model errors and recovery. Distinguish software USB re-enumeration from a physical cable pull, and audio-driver completion from independent acoustic acceptance.
4. Prepare reproducible demo media, source archive, English instructions, Chinese forum article and submission checklist. Report local preparation, public publication and official submission separately. Authentication or unavailable external forms remain attached only to publication/submission.

Verification: host endpoint/ownership/relay/FIFO tests, native firmware tests, actual normal launcher, and a bounded hardware harness using saved PCM with actual local ASR/board camera/Wi-Fi/UART. Deterministic visual responses are labeled injection; real Jev decisions are counted separately. Keep failed and successful evidence.
