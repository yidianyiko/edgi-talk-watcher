# 看守 / Watcher

作者：Oliver。基于 RT-Thread 与英飞凌 Edgi Talk 的桌面视觉看守原型。

公开源码快照不含厂商 BSP、模型权重、运行凭据、私人录音、原始测试素材和 `artifacts/`。文中 `artifacts/` 与 `testdata/` 路径描述本地证据，不是仓库内可下载的文件；依赖它们的回放和测试需要另备素材。开始使用请阅读[运行说明](docs/submission/quickstart.en.md)、[固件构建说明](docs/submission/source-build-notes.en.md)和[作品介绍](docs/submission/forum-draft.zh.md)。

The daily launcher is `.venv/bin/python -m tools.run_product --voice`. It uses the UVC camera attached to Edgi Talk, with local speech recognition and an authenticated Windows relay. Use `--camera-source pc` for the explicit PC fallback. The host must remain running; startup is paused. See [current integration and verification](docs/board-camera-integration.md) and [voice instructions](docs/board-voice.md).

Current acceptance evidence and the user-waived physical checks are recorded in [integration status](docs/board-camera-integration.md). The [PC camera relay guide](docs/pc-camera-relay.md) describes the optional fallback. Competition drafts and local packages are indexed in [submission materials](docs/submission/README.md).

一句中文设定“什么出现/消失时提醒”，持续比较画面，保存事件前后证据，并在网页和 Edgi Talk 屏幕显示状态。当前支持单目标出现/消失。

```sh
python3 -m pip install -r requirements.txt
python3 -m tools.run_product
```

打开 http://localhost:8765/，输入任务、开启摄像头、开始看守。后端从私有 `.env.local` 的 `JEV_TOKEN` 读取凭据；新任务编译需本机已登录的 Codex CLI。Jev按服务计费，图片发送到TypeSafe。只有开始看守后才采样推理。

任务及最近100条事件存在 `var/watcher/`；刷新和重启后可查看，重启默认暂停。支持单条删除和清空。模型/网络异常暂停，恢复后手动重新开始。页面后台、摄像头断开和关闭会停止采集。语音输入按浏览器能力提供，仍可输入文字。

连接实际Edgi Talk状态屏（Windows/WSL KitProg3）：

```sh
python3 -m tools.run_product --board --seconds 86400
```

启动先验证板卡桥准备就绪，桥退出则停止服务；心跳丢失后板卡显示离线。This `--board` mode provides status transport only. Use `--voice` for the managed board-camera workflow; the camera is connected to the board, and the gateway still runs on the host.

无需真人的整段录像回归：

```sh
python3 -m tools.archive_recordings --verify
python3 -m tools.replay_session testdata/recordings/hand-removal --plan testdata/plans/hand-disappears.json --responses artifacts/product-completion/recorded/hand-removal/responses-bound.jsonl --output artifacts/hand-replay-new
```

第二条需要本地保留的响应日志，零联网；不提供 `--responses` 或 `--run` 时仅离线检查。显式 `--run` 才调用真实模型。输出路径使用新目录。三段共678张原始帧及1fps无声预览保存在 `testdata/recordings/`，原始时间戳为准。

三段完整时间覆盖共67次真实Jev判断，手移除和人员出现各提醒一次，遮挡不提醒；空场景仍可能返回无法确定，不能视为准确率全部通过。详细结果及限制见 [录像评估](artifacts/product-completion/recorded/RESULTS.md)、[当前状态](CONTEXT.md)、[实现规范](docs/specs/product-completion.md)。

验证：

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
node --test tests/watcher_state.test.mjs
bash tools/build_board_status.sh
bash tools/build_board_voice.sh
```

板端固件、恢复备份和真实硬件证据见 [板端实现记录](artifacts/product-completion/board/IMPLEMENTATION.md)；私有素材、密钥和运行产物保留在本机。

板卡独立采集的网关模式（与 `--board` 互斥）：

```sh
python3 -m tools.run_product --gateway --seconds 3600
```

仅带板端令牌的上传路由开放到局域网，其余页面/历史仍限本机。启动器将作用域令牌保存在 `var/watcher/board-gateway-token`（0600），不要复制进日志。板端配置 `watch_gateway`、`watch_task` 后显式 `watch_run`；具体协议见 [网关说明](artifacts/product-completion/web/GATEWAY.md) 和 [板端记录](artifacts/product-completion/board/IMPLEMENTATION.md)。默认每次网关会话上限300秒/60次上传（参考帧及最多59次判断）；错误暂停，使用新会话重新开始。仍依赖常开的网关，Jev密钥留在网关；当前LAN HTTP限预期可信局域网。

不需要真人参与的板卡语音及电脑相机控制回归见[自动验证说明](docs/autonomous-validation.md)。
