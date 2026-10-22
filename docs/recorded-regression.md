# 录制素材与无真人回归

用户已要求后续调试默认复用录像，避免反复真人配合。任务解析、提示词、模型判定和停止逻辑先跑已存素材；新的真实场景和板端摄像头能力验证另行记录。本入口不打开摄像头、不连接板卡、不调用提示音。

## 已保留的真实素材

固定目录为 `testdata/recordings/`，与临时运行报告 `artifacts/` 分开。

| 素材 | 原始帧 | 原始首尾时间跨度 | 预览视频时长 |
| --- | ---: | ---: | ---: |
| `hand-removal/preview.mp4` | 76 | 90.572 秒 | 76 秒 |
| `person-arrival/preview.mp4` | 301 | 299.982 秒 | 301 秒 |
| `occlusion/preview.mp4` | 301 | 300.012 秒 | 301 秒 |

此前只录下约每秒一张的 JPEG，不存在可恢复的完整帧率录像。这些 MP4 是按保存帧顺序、每秒一帧重建的 H.264 无声预览；采集有停顿时，预览时间会压缩。推理回归读取原始 JPEG，帧间隔依据原始时间戳，不能用 MP4 时间推断现场耗时。

每组保留 `frames/*.jpg`、原样复制的 `frames/*.json` 时间与序号、运行/退出摘要，以及 `recording.json`。总计 678 张原始图片；索引含每张图片、每份元数据和视频的 SHA-256。`index.json` 固定完整素材清单；丢失整段素材也会校验失败。保存目录目前是本地副本，并非异地备份。

```sh
python3 -m tools.archive_recordings --verify
```

当前输出：`Verified 678 original frames, metadata and video checksums`。导出时三个视频均经过 ffprobe 全帧计数和 FFmpeg 完整解码；导出操作不修改原始采集目录。

## 任务只解析一次

```sh
python3 -m watcher.task_plan --task '当画面中原本可见的手消失时提醒我。' --output testdata/plans/new-hand-plan.json
```

当前初版仅支持**单一可见目标的出现或消失**，不限目标类别。保存原始中文、目标、变化方向、简短英文判定指令、原文指纹与 schema 版本。目标位置等限定词需要保留；预测、时长、多条件、含糊目标明确拒绝，不擅自改成支持的任务。

编译器复用本机已登录的 Codex CLI 默认模型配置，使用 `codex exec --output-schema` 和临时工作目录；只向模型提交任务文字，不提交图片或密钥。接口已核对本机 `codex-cli 0.163.0 --help` 与 [OpenAI Docs](https://learn.chatgpt.com/docs/non-interactive-mode)。外部调用限时 90 秒，失败不重试；保存后的计划无需再调用编译模型。更换编译服务可注入 translator，不需要改 Jev 请求或素材。

已经保存 `testdata/plans/hand-disappears.json` 和 `person-appears.json`，均由真实编译调用生成。股票预测任务真实调用已拒绝，记录在 `artifacts/replay-v1/unsupported-task.json`。

## 默认不联网的回归入口

```sh
python3 -m tools.replay_watch testdata/hand-cases.json --plan testdata/plans/hand-disappears.json --output artifacts/check-hand-offline.json
python3 -m tools.replay_watch testdata/person-cases.json --plan testdata/plans/person-appears.json --output artifacts/check-person-offline.json
```

默认检查图片和请求格式，`model_calls=0`、`passed=null`；这不代表模型效果通过。加入 `--run` 才会调用真实 Jev，每份清单最多 12 次，顺序执行、首个错误后停止、不自动重试。全部请求先完成本地校验。输出文件必须是新路径，避免覆盖旧实验。

```sh
python3 -m tools.replay_watch testdata/hand-cases.json --plan testdata/plans/hand-disappears.json --run --output artifacts/check-hand-live.json
```

模型仍为 `jev-1.14.0`，confidence 门槛仍为 0.8。本轮只改变任务解析与回归方式，没有训练或微调 Jev。报告分别记录严格匹配、误报、漏报。真实评估有任何标签不匹配或请求失败，`passed=false`，CLI 退出码为 1；离线检查成功退出 0，但不声称模型通过。

若需要再次做实机试验，可使用 `tools.continuous_watch --plan <已存计划> ...`。它在打开设备前验证计划，并将完整计划写入该次采集目录；不会重复编译。当前网页、`continuous_watch --task` 和 `replay_session --task` 已接入持久编译计划；旧的固定帧对探针保留用于历史案例。

## 2026-10-20 证据

| 任务 | 真实 Jev 调用 | 严格匹配 | 误报 | 漏报 |
| --- | ---: | ---: | ---: | ---: |
| 手消失 | 6 | 5 | 0 | 0 |
| 人出现 | 4 | 4 | 0 | 0 |

证据：`artifacts/replay-v1/live.json`、`person-live.json`。手消失的两组正样本均触发；仍有手的两组均无事件；遮挡返回无法确定。“两帧原本就没有手”返回无法确定，期望是无事件，因此手这一组严格验收未通过。人出现这组的进入、停留、空场景、遮挡均匹配。

这些帧来自此前用过的两个现场录制和遮挡录制，属于固定回归素材，不是独立测试集，也不代表长期准确率。两个遮挡用例是跨录制拼成的负对照，清单已标注，不冒充真实连续遮挡过程。当前是选定帧对评估，不是全视频逐帧或实际时长重放；连续状态机的截止、暂停、事件去重由注入时钟测试验证。此次没有打开新摄像头或验证新板端行为。

## 整段连续回归更新

新增 `tools.replay_session` 使用与实时网页/CLI相同的 `WatchEngine`，按原始时间10秒采样并强制覆盖尾帧。三段共67次真实Jev调用，手移除与人出现各提醒1次，遮挡0提醒；空场景仍有uncertain，不声称严格分类全部通过。三份绑定计划的响应日志零联网重放一致。详情见 `artifacts/product-completion/recorded/RESULTS.md`，与上表早期10次选定帧对评估分开。
