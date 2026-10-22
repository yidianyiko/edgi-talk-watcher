> Current integration (2026-10-22): V10 is flashed and verified. `--voice` defaults to the board USB camera; `--camera-source pc` selects the PC fallback. Voice, board frames and event announcements share one authenticated relay and one UART bridge. See [current integration evidence](board-camera-integration.md). Earlier V8/V7 sections below are historical.

# 看守功能验收状态（更新至2026-10-21）

最新V8修复并实测板端摄像头采集/Wi-Fi上传，见`docs/board-camera.md`；保留V7屏幕眼睛角色，见`docs/screen-face.md`；保留V6的事件播报链路，实体发声仍待验收，见`docs/event-announcement.md`。板卡语音已完成实板录音、Wi-Fi上传及本地识别，详见本文末尾2026-10-21更新；下文V4、75项测试与未联网是早期验收记录。

本轮执行用户“完成剩余问题，不反复真人参与调试”的要求。已完成可由当前软件环境推进的实现和验证；独立板端设备验收受摄像头物理连接和无线接入条件限制。

| 剩余事项 | 实现与证据 | 尚未成立的结论 |
| --- | --- | --- |
| 整段录像连续验证 | 三段678帧归档校验；原始时间10秒采样含尾帧，67次真实Jev，手移除/人出现各1提醒，遮挡0提醒；绑定响应日志零联网重放一致 | 非逐帧模型评估；空场景仍有uncertain；非独立泛化集 |
| 中文任务统一入口 | 网页、continuous_watch和replay_session统一编译缓存计划，模型异常明确暂停；当前支持单目标出现/消失 | 不支持预测、时长及多条件，不是任意任务理解 |
| 板端摄像头+联网 | UVC/WHD/lwIP、有限采图上传、令牌/会话/预算已实现；V4实板烧录读回一致；Wi-Fi扫描曾成功；主机网关真实HTTP+真实Jev返回event并保存 | 板端无UVC枚举，Wi-Fi未关联，板端实际采图→无线上传→模型→LCD完整链路未验收；仍依赖网关 |
| 屏幕与控制 | 任务/计数/状态/四操作协议、触摸入口实现；V4实板协议及五状态/超时自动测试通过 | 触摸实际点击、实体屏幕视觉效果未验证；独立模式开始用显式watch_run，触摸start是控制请求 |
| 历史与证据 | SQLite持久任务/事件/前后图，100条上限、删除清空、刷新和进程重启恢复，经实际浏览器验证 | 非异地备份；不提供跨设备历史同步 |
| 长运行与恢复 | 暂停/切换旧结果失效、错误手动恢复、后台/断连停止、重启默认暂停、板桥准备及退出监控完成；见连续复测记录 | 五分钟及有限自动重启不证明24小时或全天候可靠性 |

可选浏览器语音输入已接入能力检测及文字回退，仅模拟回调测试通过，未作真实ASR或板端麦克风验收。

## 本轮检查

- `python3 -m unittest discover -s tests -p 'test_*.py'`：75 tests，OK，Linux跳过1项Windows共享语义；该项另用实际Windows Python执行，1 test OK。
- `node --test tests/watcher_state.test.mjs`：5 pass。
- 自动Chromium使用虚拟摄像头及确定性模型，验证任务、去重、图片持久化、刷新、进程重启默认暂停、错误停止与手动恢复、清理、移动端和模拟语音；JavaScript错误0。详见 `artifacts/product-completion/web/browser-report.json`。
- 原生C产品/状态/HTTP预算测试及ASan/UBSan通过，M55组合固件构建成功。独立review修复跨会话竞态、任务ID、LAN路由、模式冲突及本地租约时间，修复后复审未发现should-fix。
- 实际LAN监听：非回环客户端GET首页403，带板端令牌首帧POST200 watching0，0模型调用，进程按时退出。证据 `artifacts/product-completion/runtime-gateway/report.json`。
- 新网关真实HTTP与Jev：保存的手在/手移除JPEG转板端YUYV格式上传，首帧watching0，第二帧event1，confidence0.98，实际1次模型调用，事件落盘；没有经过板卡或Wi-Fi。证据 `artifacts/product-completion/web/gateway-real/report.json`。
- 当前V4固件 `watch-product-net-20261020-4`，969632字节，SHA256 `1aeebfe9972aad0091582896bff77250f02a0b71ee1e627b73e5c6f8edfd0e34`；真实flash verify contents match。`v4-real-protocol.txt` 与 `v4-selftest.txt` 记录通过。
- `watch_network`：driver registered，connected0 ready0；`watch_capture`：no_uvc_device；配置测试用非真实令牌后watch_run明确not_ready，没有假装启动。电脑WLAN当前断开，没有可直接复用的当前Wi-Fi连接凭据。

## 启动与资源条件

网页/电脑摄像头：`python3 -m tools.run_product`；实际UART状态屏：加`--board`。板端采集网关：加`--gateway`，两种板端模式互斥。网关scope令牌仅保存私有文件，普通页面/历史限本机，板端上传走预期可信LAN的HTTP。默认网关会话300秒/60次判断，独立运行显式有界，错误不自动重试。

要完成独立板端硬件验收，需在板端应用USB host接入可枚举的UVC摄像头，并让板端关联可达网关的Wi-Fi；随后使用现有watch_capture/watch_network/watch_run即可验证，无需真人反复表演，镜头可对固定素材或保存视频屏幕。物理触摸和屏幕观感另作一次实际确认。这些物理动作无法通过当前PC串口代做。

原始录像、失败运行及修复前输出保留，不覆盖为成功报告。恢复备份、刷写范围和网关协议见 `docs/board-status.md`、`artifacts/product-completion/board/IMPLEMENTATION.md`、`artifacts/product-completion/web/GATEWAY.md`。

## 五分钟连续复测（已完成）

真实本机HTTP监听运行300.79秒，922次请求、437次注入模型调用，4次服务实例重建、6次注入超时后显式手动恢复（由自动脚本执行）。事件达到100条并保持上限，重建后任务/历史恢复且默认暂停；采样文件描述符5–6，未观察到持续增长。模型与相机是模拟，真实进程重启另由浏览器流程验证。这是五分钟有界软件复测，不是24小时硬件长测。证据：`artifacts/product-completion/soak/report.json`及`run.py`。

首轮因测试图片尺寸错误、模型调用为零而作废，保留在`invalid-report.json`，最终通过要求同时断言模型调用数、事件上限和预期错误恢复次数，未用首轮充当成功。

## 更新：电脑摄像头中转及实际Wi-Fi（2026-10-20）

用户决定转接头到货前保留电脑摄像头。已实现独立CLI中转至统一服务和事件历史，板卡继续通过UART显示状态；实体摄像头有界采集正常释放，保存录像经真实模型产生事件并持久化，pause/next无需浏览器即可停止中转。最终Python回归82 tests OK（Linux跳过1项）。详见`docs/pc-camera-relay.md`。

以上早期“Wi-Fi未关联、未提供凭据”现已更新：按用户授权安全读取Windows保存的Wi-Fi凭据，实板指定SSID关联成功；独立复查connected=1、ready=1、DHCP IP[private DHCP address]。凭据仅在私有`.env.local`，未写入日志。证据`artifacts/pc-relay-validation/wifi-ready.json`。尚无板端实体摄像头，独立板端采图无线上传仍未验收。

## 更新：板卡语音命令（2026-10-21）

已实现：SPEAK触摸/串口共用录音入口→6秒PDM麦克风录音→Wi-Fi→Windows仅音频鉴权中转→WSL本地中文ASR→设置单目标任务/暂停/继续→屏幕状态与网页转写。使用已有模型，不训练；首次准备下载校验本地ASR文件，运行时不需要新云端密钥。使用方法见`docs/board-voice.md`。

新鲜实板证据：最新V5固件1,009,732字节，flash verify contents match；mic/audio/touch/wlan均registered，Wi-Fi connected/ready。通过Windows扬声器播放保存的“暂停看守”合成语音，实际板卡采集192000字节PCM后无线上传，本地ASR返回“暂停看守。”，HTTP200，板卡DONE action=pause/http=ok。留档WAV为6秒16kHz monoPCM16，RMS370、peak9157；详见`artifacts/board-voice/microphone-smoke.json`、`hardware-smoke-final.log`。这不是用户真人说话或口音/远场识别率验收，SPEAK物理触摸点击也未实际确认。

实际电脑摄像头验证：保存的任务/暂停/继续/暂停4条语音，经本地ASR和既有缓存任务，均HTTP200；两次相机会话各首帧进入统一服务、退出0，0次视觉模型调用。暂停已使session失效，摄像头清理再次发送旧session暂停收到409，并不会恢复旧任务；报告的pause_delivery_failed即此清理回执。详见`managed-camera-smoke.json`。

验证：`.venv/bin/python -m unittest discover -s tests -p 'test_*.py'`运行111项，OK、WSL跳过1项，该Windows专属项另用实际Windows Python执行OK。JS5项、Chromium完整流程（虚拟相机/注入识别和模型、0JS错误）、5组原生C测试、音频I2C0依赖检查通过。4份保存语音有SHA-256清单，实际ASR回归含实板录音、3条合成语音及噪声拒绝。

实板验证揭示并修复：音频注册时编解码器缺I2C0导致启动断言；真正音频pipe默认阻塞导致空输入无截止；Windows中转配置前心跳过旧导致启动即退出；录音前后环境声影响ASR，启用VAD后同一存档正确。失败产物与红绿测试均保留，见`docs/lessons.md`。旧版“无板卡麦克风验收”已由上述证据更新；独立板端摄像头和触摸观感待验边界仍保留。

实际生产启动器语音模式运行12秒后退出0；UART从BOARD READY到9次paused ACK，再确认BOARD STOPPED offline；Windows中转随父进程停止。证据`artifacts/board-voice/launcher-smoke.log`及`artifacts/product-runtime/20261020T162307Z/board.log`。


## 无人参与实板扩展验证（2026-10-21）

通过已存合成语音的扬声器回放，设置任务、暂停、继续均已经过实际板卡麦克风→Wi-Fi→本地ASR执行成功。6次串口操作含连接不可用和恢复后重试，最终busy均归零；保留5段新实板录音及SHA-256。设置任务/继续各启动真实PC摄像头一次，两次均正常退出。此轮使用缓存任务和固定视觉响应，不是新Jev评估。证据与无需真人的复测方式见`docs/autonomous-validation.md`、`artifacts/voice-autonomous/report.json`。


超时扩展实测也通过：测试服务实际收到192000字节音频后不响应，板卡在传输120秒截止处返回`stage=read-wait err=-2`，最终FAILED且busy=0。整条串口测试含准备和录音共135.17秒；恢复网关地址后再次实际录音，ASR暂停命令成功。证据`artifacts/voice-autonomous/timeout-report.json`、`timeout-serial.log`、`timeout-recovery.log`。未断开Windows网络；故障注入是独立服务不响应。
