# Submission checklist and evidence boundaries

## Prepared locally

- [x] Chinese forum draft with the user-provided `〖2026嵌入式大赛〗` title prefix.
- [x] English setup, workflow, scope and offline replay instructions.
- [x] Captioned 60-second demonstration assembled from preserved real images.
- [x] Source provenance / SHA-256 manifest and an allowlisted presentation ZIP.
- [x] Candidate submission fields prepared. Participant: Oliver; contact supplied and stored only in private `var/submission/participant.json`, excluded from public packages.
- [x] Explicit separation of physical-board results, PC recording evaluation and reconstructed presentation media.

## External completion gates

- [ ] Read the actual official announcement and current submission sheet in an authenticated browser if required. Automated fetch on 2026-10-22 returned HTTP468 for the announcement; the Tencent sheet was inaccessible. No exact required fields, eligibility details or media constraints were inferred.
- [ ] Confirm official deadline and title/category against those pages. User-provided schedule: internal 10/30, official 11/1. Search-index listings include other similarly named competitions and must not be substituted for this announcement.
- [x] Participant name and contact supplied by the user; private contact retained locally.
- [ ] Publish source and verify its public URL.
- [ ] Add a public video URL or upload the existing file as the form permits.
- [ ] Publish the reviewed forum article through an authorized logged-in account, then record its real URL.
- [ ] Fill the actual sheet/form and retain a readback/receipt. A local ZIP or HTTP200 from an unrelated page does not establish entry acceptance.

No public article, public upload or submission-sheet write was performed for this package.

## Current integrated runtime

The normal voice launcher now defaults to the board USB camera; PC fallback requires `--camera-source pc`. See [the current integration report](../board-camera-integration.md). V10 source/native/linked review and flash verification are complete. Fresh V10 acceptance passed seven clean starts/stops including injected model failure and actual relay-process loss/restoration, a 300-second-budget soak (53 archived frames, 51 controlled decisions, one event), and three saved-PCM start/pause cycles through the normal launcher. Recovery included one real Jev comparison; controlled decisions remain explicitly labeled. See [machine-readable acceptance](../../artifacts/board-integration/acceptance-report.json). V9 faulted during its final stop and remains failed evidence. These current passes come from the new reports, not the historical presentation.

## Sources and freshness

The user supplied [official announcement](https://club.rt-thread.org/ask/article/c92780a184b3c077.html), [submission sheet](https://docs.qq.com/sheet/DTmdVWEFkZmxXaVpl?tab=000001), [board documentation](https://www.rt-thread.org/document/site/#/rt-thread-version/rt-thread-standard/hw-board/psoc-e84-edgi-talk/psoc-e84-edgi-talk) and [BSP](https://gitee.com/RT-Thread-Studio-Mirror/sdk-bsp-psoc_e84-edgi-talk). Announcement/form content was not retrieved successfully; those links identify destinations, not verified rule quotations.

The presentation's hardware sources are the V8 board-camera checkpoint on 2026-10-21 and V7-era screen readback. The recorded event pair is an earlier actual PC-camera evaluation. The video is deliberately historical: it must not be used as evidence of the later integrated runtime or unplug/replug acceptance.

## Reusable evidence

| Claim | Actual evidence | Limit |
| --- | --- | --- |
| Real board capture and Wi-Fi upload | `artifacts/board-camera/gateway-report.json`, two YUYV files | Two uploads / one Jev `uncertain`; no board event in this test |
| Hand-removal event | `artifacts/product-completion/recorded/hand-removal/events/1/` | PC camera, saved frames, existing fixed recording |
| Real display content | `artifacts/board-face/screen-still.png` | Framebuffer readback, not external optical video |
| Current daily integration | `docs/board-camera-integration.md` | V10 recovery/soak/launcher passed within report scope; further physical checks waived by user; no unperformed check is claimed passed |
| Existing software robustness | Current project's test and acceptance reports | Do not infer physical unplug recovery or 24h reliability |

The package is deliberately allowlisted. It excludes private `.env.local`, gateway-token files, runtime proxy configurations, original serial logs, databases, voice recordings and raw firmware backups. It is not a replacement for a complete reviewed source release.

## User scope decision (2026-10-22)

No further physical testing is required. Cable unplug/replug, physical touch/microphone gestures and independent listening checks are waived and do not block delivery. Existing automated acceptance closes the development scope. Historical evidence limits remain unchanged. Only publication/submission actions remain in the external completion checklist.
