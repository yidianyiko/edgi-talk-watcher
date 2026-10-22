# Watcher competition package

Prepared on 2026-10-22. Public source: https://github.com/yidianyiko/edgi-talk-watcher . Participant: Oliver; contact details are retained privately and excluded from this repository. The forum article is kept locally only, excluded from the public repository and source ZIP, and has not been posted. These materials are not an official competition submission receipt.

- Local-only `forum-draft.zh.md`: Chinese forum article, excluded from public source packages.
- `quickstart.en.md`: English setup, operation and reproducible evaluation instructions.
- `submission-checklist.md`: submission status, provenance and external blockers.
- `source-build-notes.en.md`: clean-BSP build sequence and source snapshot limits.
- `../../artifacts/submission/source.zip`: allowlisted source snapshot, generated separately with `build_source_release.py`.
- `submission-fields.json`: paste-ready candidate fields. These are not claimed to be the official sheet schema.
- `../../artifacts/submission/demo.mp4`: 60-second captioned evidence presentation; silent, with explicit source labels. Saved images are held on screen, not presented as continuous live footage.
- `../../artifacts/submission/media-manifest.json`: hashes and source provenance.
- `../../artifacts/submission/package.zip`: selected documents, demo and provenance only. This is a presentation package, not a complete source-code or firmware archive.

The video deliberately uses the established V8 hardware checkpoint. The current voice launcher defaults to the board camera. New integration results belong in [the current integration report](../board-camera-integration.md) and must not be inferred from this historical video.

To reproduce media and the allowlisted presentation archive, from the repository root:

```sh
.venv/bin/python docs/submission/build_demo.py
```

Media assembly has no product behavior suitable for a failing unit test. Verification uses source hashes, image inspection, ffprobe stream/duration checks, full-file video decode and archive-content inspection.
