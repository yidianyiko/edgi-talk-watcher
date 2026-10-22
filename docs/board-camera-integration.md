# Daily board-camera workflow

The default `.venv/bin/python -m tools.run_product --voice --seconds 86400` now uses the UVC camera attached to Edgi Talk. Use `--camera-source pc` for the explicit PC fallback, or `--voice-recording <folder>` for saved-frame regression. Startup remains paused. Press SPEAK to record a task, pause or continue command; physical touch testing is waived under the user decision below.

The board sends PCM speech and 320×240 YUYV frames over the same bearer-authenticated Windows LAN relay. Local Whisper handles speech; the existing host gateway calls Jev and stores events. The device still requires the host. The UI/history is accessible only through the local host listener. Network transport is trusted-LAN HTTP.

One UART bridge owns task/status updates, bounded camera start/stop and event announcements. While the board camera runs, the firmware owns the screen state; periodic host status writes no longer cancel it. Voice success waits for an actual accepted first frame. Pause or task replacement invalidates the reservation before stopping the camera, so late frames cannot restart it. Hardware start/pause requests are consumed by the managed runtime; history requests remain available to the web page.

Each board session is limited to 300 seconds / 60 uploads: one reference frame and at most 59 model comparisons. Only newly committed events receive an announcement ID. FIFO delivery and board deduplication prevent repeated speech for a persistent event. Uncertain decisions remain uncertain.

## Saved regression material

- `artifacts/board-recordings/<session>/`: each valid received raw YUYV frame, converted JPEG, and `frames.jsonl` containing board timestamps, source and SHA256. Inputs are retained before inference, including model failures and discarded results.
- `artifacts/board-camera-sessions/<run>/summary.json`: bounded lifecycle outcome.
- `var/watcher/voice/`: original uploaded WAV clips; opaque filenames.
- Existing `testdata/recordings/` and `testdata/voice/` remain intact.
- The actual V10 soak archive is `artifacts/board-integration/soak/recordings/f630d909b09c4fc780101c833fba191d_1/`: raw/JPEG samples plus `recording.json` compatible with the existing offline replay loader. `preview.mp4` is a silent 53-second sampled preview, one image per second, not full-rate footage. Full video decode and deterministic offline replay completed successfully; `soak/archive-verification.json` records its hash. The replay injected decisions and made zero network calls.

## Firmware and recovery

Flashed image: `watch-product-voice-20261022-10`, 1,039,160 bytes, SHA256 `a930c9df454af0b10af35529232943e6048bf67df48506f5d3d4511cc371a87b`. Actual flash verification is `artifacts/board-integration/flash-v10.log` (`contents match`). M33 is unchanged; M55 writes bank2 offset `0x580400`, sectors22–25.

A valid 1MiB V8 rollback image was read and verified before flashing: `artifacts/board-integration/before-v9-flash1m.bin`, SHA256 `7e7690494bb8cf7044277d5a8e27a03cb8d0654a60a9f14ab8994a697fdd4cbd`. Its +0x400 region matches the archived V8 binary. Restore the whole backup at bank2 `0x580000`, not `0x580400`.

A second verified 1MiB rollback snapshot before V10 is `artifacts/board-integration/before-v10-flash1m.bin`, SHA256 `8cb72c6f0a90d564059d24dd6080a71200be3babd89a08a767b5aa63fd1d3a40`; its +0x400 region matches the archived V9 image. V9 remains a diagnostic checkpoint with the failed shutdown described below; V8 is the earlier limited-capture checkpoint.

V8 successfully captured a first session but repeat opening failed with USB IO error -12. Two independent actual-hardware runs reproduced it; failure logs and images are retained. V9 uses the BSP's public USB deinitialize/initialize APIs before the bridge's first capture and between completed sessions. This is USB-host recovery; the proprietary driver's underlying stop/reopen defect is not claimed fixed. Reset rejects an active capture and polls camera discovery for at most eight seconds; that bound excludes synchronous vendor calls. No automatic paid model retry is added.

### Verified V10 shutdown correction

The V9 fault dump places the interrupted camera thread in `usbh_kill_urb` while its restored interrupt executes `USBH_IRQHandler` with a null channel URB. The proprietary driver leaves a channel-halted interrupt enabled when DMA is active and CHENA is already clear. Separate disassembly also shows a callback can resubmit the first URB between the two cancellations. The flashed V10 correction serializes stream stops, keeps synchronous video close interruptible, masks USB IRQ during paired cancellation, and clears/masks stale channel events before restoring the previous IRQ state.

The V10 voice build suppresses the vendor automatic stop/delay/restart recovery worker. Camera failures instead end the bounded application session; the next explicit start performs USB-host recovery. This preserves one lifecycle owner and adds no automatic paid model retries. The native regression, seven-session physical recovery run, 300-second-budget soak and normal-launcher repeats below establish the tested scope of this correction.

## Verification

Current evidence is in `artifacts/board-integration/`. Host tests: 127 run, 126 passed and one Windows-only case skipped; that case passed independently with installed Windows Python. JavaScript: five passed. The V10 build ran ten native test groups and completed successfully. Independent host and recovery review is recorded in `host-review.md`; V10 source/native/linked review is in `review-v10.md`.

The earlier V9 actual hardware acceptance reached seven successful voice starts, including recovery after an injected model failure and an actual LAN-relay outage. The final USB stream stop hard-faulted in `rt_sem_release`; this run failed. The UART log, raw camera frames, matching ELF, registers and stack dumps are preserved in `artifacts/board-integration/`. This is preserved failed evidence; the separately identified V10 recovery and soak below supersede it for the corrected build. The V10 recovery run completed seven actual voice starts and seven clean camera stops, including an injected model failure and actual authenticated-relay process loss/restoration. Board process exit was zero; four controlled events each produced one PLAY/DONE cycle. One actual Jev comparison returned `uncertain` (confidence 0.83). Evidence: `hardware/report.json`, its seven session summaries, `serial.txt` and `real-jev-response.json`. The V10 300-second-budget soak also passed: 53 valid received raw frames, all SHA256 checks matched, 51 controlled decisions, one event and one PLAY/DONE cycle. The final upload was rejected with HTTP409 when the gateway deadline expired, followed by a clean stop and board process exit zero. Board timestamps span 285.213 seconds; the full harness including setup/cleanup took 352.914 seconds. This is a bounded sampled-camera test. The actual default `tools.run_product --voice --seconds 86400` launcher then passed three saved-PCM start/pause cycles through local ASR, with actual first board frames and three `paused` session summaries. The service is left running and paused at http://localhost:8765/; its process/lease metadata is in `runtime-cli-pid.json`. Controlled visual responses are distinct from real Jev inference. Audio `PLAY/DONE` proves driver control flow; no independent physical microphone is available on Windows (only the virtual DroidCam endpoint), so speaker loudness/clarity has no independent acoustic evidence; further physical testing is waived. USB-host re-enumeration is distinct from physically pulling and reconnecting the camera cable.

Final machine-readable acceptance: [acceptance-report.json](../artifacts/board-integration/acceptance-report.json). Failed V9 evidence is retained in `hardware-v9-shutdown-failure/`; the current passing run uses `hardware/`.

## Acceptance scope decision (2026-10-22)

The user explicitly requested no further physical testing. Physical cable unplug/replug, final touch/microphone gesture checks and independent speaker listening checks are waived, not pending acceptance tasks. Existing automated acceptance is sufficient for the current delivery. This decision does not turn unperformed checks into passed results. Long-duration reliability remains an evidence limit, not an outstanding test requirement. Public publication/submission remains separate.
