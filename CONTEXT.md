# 看守

用一句中文定义视觉目标的出现或消失，事件发生时提醒并保留前后画面。目标不限类别；目前拒绝预测、时长、多条件等任务，不做专用模型训练。当前完成规范见 `docs/specs/product-completion.md`。

用户要求：持续完成剩余功能，默认复用已存录像调试，不再反复要求真人表演。素材是 `testdata/recordings/` 三段共678张原始JPEG及时间戳；MP4是1fps无声重建预览，不能当原始全帧率录像。

## 当前软件

- 中文任务编译一次并持久缓存；网页、连续看守CLI和整段录像入口使用经过校验的计划。
- `WatchEngine` 统一参考帧、30秒过期、事件去重、uncertain锁存、暂停/旧结果失效、截止和调用预算。
- 网页任务、事件及前后画面存SQLite，最多100条事件；可删除，刷新/服务重启恢复上次任务，默认暂停。错误暂停并手动重试；后台、关闭、设备断开停止采集。
- 网页与Edgi Talk显示任务、状态、事件计数；板卡有开始、暂停、切换、历史操作协议和触摸入口。真实触摸操作尚未验证。
- 板卡新增SPEAK触摸入口、6秒录音、Wi-Fi音频中转、本地中文ASR、任务/暂停/继续与屏幕反馈；`.venv/bin/python -m tools.run_product --voice` 自动连接Wi-Fi和状态桥，见`docs/board-voice.md`。浏览器原有语音输入仍是浏览器可选能力。
- 服务端密钥仅从环境或私有 `.env.local` 读取；固定Jev `jev-1.14.0`、confidence门槛0.8，不把模型错误解释成无事件。

## 已有真实证据

完整时间覆盖三段录像，每10秒左右采样并包含尾帧；67次真实Jev调用：手消失9次判断1次提醒，人出现29次判断1次提醒，遮挡29次判断0次提醒。没有额外误报，但手移除后的空场景8轮及所有遮挡轮返回uncertain，严格分类并未全部通过。不是678帧逐帧判断，也不是独立泛化测试集。响应日志可零联网重放。详见 `artifacts/product-completion/recorded/RESULTS.md`。

Current flashed firmware is V10 `watch-product-voice-20261022-10`, 1,039,160 bytes, SHA256 `a930c9df454af0b10af35529232943e6048bf67df48506f5d3d4511cc371a87b`; OpenOCD verify_bank reports contents match.先前V4的任务、计数、非法输入、四操作请求、五种状态、心跳超时实板自动测试通过。板端Wi-Fi已按用户授权复用Windows保存的Wi-Fi凭据关联，独立复查connected=1、ready=1、已获得局域网IP；私有配置不回显密码。板端USB摄像头现已枚举，V8连续两次单帧采集成功；实际板端采集→Wi-Fi→网关→一次真实Jev已通过，详见`docs/board-camera.md`。

## 边界

电脑摄像头+Jev+UART显示是已验证的原型通路；不能称为完全独立设备。板端摄像头→局域网网关上传现已用真实板卡采集、Wi-Fi与一次Jev判断验证（uncertain，无事件），见`docs/board-camera.md`。此前使用保存JPEG转换YUYV的网关测试是历史证据，不能混同本次实板采集。屏幕framebuffer可读回，协议ACK不等于已观察实体屏幕观感。采样会漏掉间隔内短暂事件；固定录像通过不代表长期无人值守可靠性。

历史现场采集、早期错例及状态桥保留在 `docs/continuous-watch.md`、`docs/board-status.md`、`docs/recorded-regression.md`，最新汇总以本文件和本轮验收报告为准。

此前功能完成轮软件验证：75项Python通过（Linux跳过1项，已另用Windows Python实测通过），JS5项通过，真实浏览器流程无JS错误。五分钟HTTP模拟模型复测300.79秒、922请求、4次服务实例重建、6次故障恢复，事件100条上限、FD5–6；边界与全部证据见 `docs/product-status.md`。V4实板状态自测和10秒实际启动器运行均退出0。

此前决定摄像头暂留电脑；现用户已把摄像头连接板卡，硬件通路验证见下文。`tools.pc_camera_relay`已将实体PC摄像头接入统一服务API与持久历史，实测正常退出；不依赖浏览器操作。板卡pause/next可停止中转。已从Windows保存的Wi-Fi配置安全读取Wi-Fi凭据到私有`.env.local`字段WIFI_SSID/WIFI_PASSWORD，连接脚本`tools/connect_board_wifi.ps1`不回显串口内容；实板已联网，复查证据见`artifacts/pc-relay-validation/wifi-ready.json`。详情见`docs/pc-camera-relay.md`。

## 板卡语音验收更新（2026-10-21）

最新实板录音6秒（192000字节PCM，16kHz mono16）经Wi-Fi与Windows受鉴权中转到WSL本地ASR，识别“暂停看守。”，板卡返回DONE action=pause/http=ok；用Windows保存的合成指令扬声器回放完成，没有要求真人说话。板卡采集的完整WAV已留档并纳入离线识别回归。完整证据`artifacts/board-voice/microphone-smoke.json`、`hardware-smoke-final.log`。

另用保存的任务/暂停/继续语音，通过实际本地ASR与真实PC摄像头验证设置任务、暂停、继续及释放；2次相机会话均首帧进入统一服务，正常退出，无视觉模型调用。使用已有缓存计划，不能把此项当作新任务真实编译或新视觉模型评估。见`managed-camera-smoke.json`。语音发起看守每次仍限300秒/60次判断；屏幕仅ASCII，中文转写在网页。实际SPEAK触摸点击、不同用户口音和噪声条件下识别率仍待验。

最新完整软件回归111项，WSL跳过1项Windows专属文件共享语义，该项用Windows Python另测通过；JS5项、实际浏览器与5组原生C测试及音频启动依赖检查通过。失败固件、全零无效备份、传输失败和误识别日志均保留，不能充当通过证据。原先75项/V4记录是历史。


## 无人参与实板扩展验证（2026-10-21）

通过已存合成语音的扬声器回放，设置任务、暂停、继续均已经过实际板卡麦克风→Wi-Fi→本地ASR执行成功。6次串口操作含连接不可用和恢复后重试，最终busy均归零；保留5段新实板录音及SHA-256。设置任务/继续各启动真实PC摄像头一次，两次均正常退出。此轮使用缓存任务和固定视觉响应，不是新Jev评估。证据与无需真人的复测方式见`docs/autonomous-validation.md`、`artifacts/voice-autonomous/report.json`。


超时扩展实测也通过：测试服务实际收到192000字节音频后不响应，板卡在传输120秒截止处返回`stage=read-wait err=-2`，最终FAILED且busy=0。整条串口测试含准备和录音共135.17秒；恢复网关地址后再次实际录音，ASR暂停命令成功。证据`artifacts/voice-autonomous/timeout-report.json`、`timeout-serial.log`、`timeout-recovery.log`。未断开Windows网络；故障注入是独立服务不响应。

## 事件语音提醒更新（2026-10-21）

已接入新事件→FIFO/确认→真实UART→板卡固定中文提示语，实板去重、播放期间录音互斥和播放后实际录音/ASR恢复通过。114项Python、Windows专属1项、JS5项及6组原生C检查通过。外部录音未可靠确认目标提示语，实体扬声器实际发声/音量/清晰度仍未验收，不能用PLAY/DONE代替。当前只覆盖电脑摄像头统一事件路径；完整证据与恢复说明见`docs/event-announcement.md`。

## 屏幕角色更新（2026-10-21）

V7增加随状态变化、眨眼和左右看的两只眼睛，实际刷写校验及framebuffer读回完成，原任务/按钮保留。114项Python（另测Windows专属项）、JS5项、7组原生C及独立review通过。本轮实际录音先识别失败，保存音频复测DONE pause/http=ok；保留失败与成功WAV，不能据此称噪声条件下稳定。详见`docs/screen-face.md`。

## 板端摄像头更新（2026-10-21）

V8修复BSP帧队列接收信号量初始值错误（空队列误唤醒导致启动过早清理）。实板连续两次watch_capture通过、每帧153600字节；板端watch_run经实际Wi-Fi上传两帧、一次真实Jev返回uncertain，无事件。原始YUYV、JPEG和稀疏重建MP4留档，见`docs/board-camera.md`。这是有界诊断脚本，日常`--voice`启动器仍使用PC采集监督器；尚未把语音start自动切换到板端摄像头，不能称为完整板端产品模式。


## Current integrated acceptance (2026-10-22)

The normal voice launcher uses the board USB camera; the PC camera is an explicit fallback. V10 fixed a reproduced USB cancellation interrupt race and suppresses the vendor's competing automatic recovery worker. Actual acceptance passed seven start/stop sessions including model/relay failure recovery, then a 300-second-budget soak, then three start/pause cycles through the normal launcher. Controlled visual decisions are labeled; one real Jev decision in the passing recovery run returned uncertain. All board frames are preserved with hashes, and the soak has an offline replay archive and silent sampled preview. See `docs/board-camera-integration.md` and `artifacts/board-integration/acceptance-report.json` for exact counts and limits. The launcher is left running, paused, with a 24-hour service lease; this is not a 24-hour reliability acceptance. Further physical testing (independent audibility and physical touch/unplug checks) was explicitly waived by the user on 2026-10-22; these are no longer acceptance blockers. Existing automated acceptance closes the current development scope. Public competition submission remains separate.

## Source publication (2026-10-22)

User authorized GitHub source upload. The reviewed source snapshot is published at https://github.com/yidianyiko/edgi-talk-watcher . Participant name is Oliver; contact details remain only in private `var/submission/participant.json`. Forum article is kept locally only in `docs/submission/forum-draft.zh.md`, excluded from public source and source ZIP, and is not posted and the official entry has not been submitted. Public source excludes credentials, recordings, private scenes, vendor BSP and runtime artifacts.
