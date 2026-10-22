> Current integration (2026-10-22): V10 is flashed and verified. `--voice` defaults to the board USB camera; `--camera-source pc` selects the PC fallback. Voice, board frames and event announcements share one authenticated relay and one UART bridge. See [current integration evidence](board-camera-integration.md). Earlier V8/V7 sections below are historical.

# 板卡语音命令

点击 Edgi Talk 屏幕的 `SPEAK`，录6秒语音，通过 Wi-Fi 发到电脑本地识别。说“暂停看守”“继续看守”，或“有人进入画面时提醒我”这类单目标出现/消失任务。新任务仍走既有任务校验，拒绝预测、时长和多条件任务。The default camera is now the UVC camera attached to the board. Local ASR needs no additional service key; visual decisions continue to use Jev.

## 启动

当前 Windows/WSL 环境、已刷入对应语音固件的板卡：

```sh
.venv/bin/python -m tools.run_product --voice --seconds 86400
```

浏览器打开 http://localhost:8765/ 查看识别文字、任务和事件。启动器读取私有 `.env.local` 的 `WIFI_SSID`/`WIFI_PASSWORD` 连接板卡，自动选择 Windows 物理网卡 IPv4；多个地址时使用 `--voice-host <Windows局域网IPv4>`。语音端口默认8766，可用`--voice-port`改动。令牌自动生成并只保存在私有数据目录，不用手工复制。语音模式包含 UART 状态桥，与独立摄像头 `--gateway` 模式互斥。

第一次准备本地识别环境：

```sh
uv venv --system-site-packages .venv
uv pip install --python .venv/bin/python -r requirements-voice.txt
.venv/bin/python -m tools.setup_local_asr
```

下载器按 `tools/asr_model.json` 固定版本和 SHA-256 校验4个模型文件，已有正确文件仅检查，不重复下载。默认路径`var/models/whisper-base`；设置`WATCHER_ASR_MODEL`可使用另一份兼容本地模型。运行期间不自动联网下载模型。新视觉任务编译仍需本机既有编译器环境。

## 操作与保存

- 屏幕显示 `LISTENING`、`RECOGNIZING`、`DONE` 或 `FAILED`；成功显示 `PAUSE`/`START`/`TASK`。现有字库仅支持 ASCII，完整中文转写在网页查看。
- 没有录到话、识别不确定、服务不可达或相机启动失败均报失败；可再次点击。不会把空录音当成功，也不会后台常听。
- Board-camera voice sessions use at most 300 seconds / 60 uploads (one prime frame and at most 59 model comparisons)，到限后暂停，可再说“继续看守”。重复继续不会重复占用相机，新任务等旧相机释放后启动。网页关闭不暂停板卡发起的看守；可用语音或板卡暂停操作。
- Audio remains in `var/watcher/voice/*.wav`. Board frames (raw YUYV, JPEG, timestamps and hashes) are archived in `artifacts/board-recordings/`; lifecycle summaries are in `artifacts/board-camera-sessions/`. PC fallback frames remain in `artifacts/voice-camera/`.`--data-dir`可更改任务、语音、私有令牌目录。
- 退出时停止相机、串口桥和 Windows 中转；父进程心跳丢失后中转自动退出。重启默认暂停，语音网关在启动时重新配置到板卡 RAM。

The relay exposes only bearer-authenticated `POST /api/board/voice` and `POST /api/board/observe`，不开放网页、历史或通用代理。音频为16kHz单声道PCM16，最大8秒。当前为预期可信局域网 HTTP。

## 构建与回归

```sh
bash tools/build_board_voice.sh
.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
node --test tests/watcher_state.test.mjs
```

Current V9 adds USB host reinitialization between sessions; firmware output is `artifacts/board-voice/watcher-voice-v9.bin`.M33保持原样，M55仅写bank2偏移`0x580400`所在的四个扇区22–25。先验证映像大小和备份，刷写后读回校验；刷写不属于上面的启动命令。原V4恢复备份、启动断言修复前映像、失败日志和测试语音均保留，实际验收见`docs/product-status.md`。

稳定回归语音位于`testdata/voice/`（含实际板卡采集的回放语音和SHA-256清单），原始合成语音也保留在`artifacts/board-voice/speech/`，用于无真人识别回归；它们不能证明真实用户口音、远场或噪声条件下的识别率。网页自动测试也使用虚拟相机与注入识别，应与实板麦克风证据区分。

无人参与的实板命令循环、故障及恢复回归见[自动验证说明](autonomous-validation.md)，包含实际扬声器回放与麦克风录音的证据边界。

事件后板卡固定中文提醒已接入V6；去重、排队及录音恢复已实测，实体发声效果仍未确认。详情见[事件语音提醒](event-announcement.md)。
