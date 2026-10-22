# Source snapshot and clean-BSP build

`artifacts/submission/source.zip` is an allowlisted source snapshot. Its embedded `SOURCE-MANIFEST.json` lists the exact files, sizes and SHA-256 digests. It includes the root `watcher/`, `tools/`, `firmware/`, `tests/`, `docs/`, `AGENTS.md`, `CONTEXT.md`, `README.md`, requirement files and the runtime dependency `research/*.py`. Research fixture PNGs are excluded. The forum article `docs/submission/forum-draft.zh.md` is local-only and excluded. It excludes the vendor BSP, `.env*`, runtime data, compiled binaries/caches, original scenes, test recordings and all existing artifacts. This reduces accidental disclosure; it does not transfer vendor rights or provide a full offline distribution.

## Dependencies and reproducibility limits

The BSP revision expected by both firmware build scripts is:

```
b135be8a28127e276a04b70d27950c3ba07b917a
```

Obtain the BSP from the [project's official mirror](https://gitee.com/RT-Thread-Studio-Mirror/sdk-bsp-psoc_e84-edgi-talk), place it at `vendor/edgi-talk-bsp`, and check out that revision. A default shallow clone in `build_board_status.sh` only succeeds if its HEAD matches the pinned revision; if upstream HEAD has moved, obtain the pinned commit before running the scripts. Neither script silently accepts a new BSP revision.

Use the established ARM GCC toolchain, `scons`, host C compiler and Python dependencies. Host setup and local ASR preparation are in `quickstart.en.md`. ASR model files are downloaded separately with the pinned hashes in `tools/asr_model.json`.

The voice build reads its generated base project `Edgi_Talk_M55_Watcher`, which the status build creates from the official UVC example. Therefore run these **sequentially** on a clean BSP:

```sh
bash tools/build_board_status.sh
bash tools/build_board_voice.sh
```

Do not run those builds concurrently: the vendor tree shares generated objects. The voice build validates/applies `firmware/patches/camera-empty-queue.patch`, copies root-owned firmware sources into its generated project and checks the final image against the slot limit. Builds do not flash hardware. Use `docs/board-status.md` for backup and verified recovery procedures.

This source-only archive intentionally does not include `testdata/`. Tests or replay commands that require saved camera/voice fixtures need that separately reviewed fixture set; the archive alone must not be described as a complete offline test suite. Existing firmware embeds a prerecorded notification as C source, which is included as project source. Raw private WAV recordings and scene images are excluded.

## Verify archive

Run the source builder from the project root:

```sh
.venv/bin/python docs/submission/build_source_release.py
```

It rejects symlinks and unrecognized file extensions, reads only the explicit source allowlist, validates textual UTF-8 content and checks credential-shaped assignments without reporting their values. It never reads `.env.local`, runtime token files or private data directories. The ZIP excludes itself and generated manifests. Its verification report records SHA-256, ZIP integrity, file counts and the scope checks.

The snapshot represents file contents at packaging time. It does not establish a clean-room rebuild, real-board acceptance, public publication or competition submission.
