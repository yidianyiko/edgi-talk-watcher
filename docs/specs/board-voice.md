# 板卡按键语音命令

用户已确认并要求实现：点屏幕后说话→板卡录音→Wi-Fi送电脑识别→执行命令→屏幕反馈。复用电脑摄像头、现有任务/历史与Jev判断，不训练模型。第一版支持设置单目标出现/消失任务、暂停、继续；触摸入口每次录6秒，调试命令支持1..8秒，不后台常听，不加唤醒词或播报。中文识别在电脑本地执行，模型下载后不需另配云端密钥。录音留档供离线回归。

板端在原有控制区加入SPEAK，显示LISTENING/RECOGNIZING/DONE/FAILED，识别文字在电脑网页可查。当前板屏字库仅ASCII，命令结果显示START/PAUSE/TASK及现有任务标签，不声称支持中文字库。

## 接口与验收

- `POST /api/board/voice`：Bearer BOARD_GATEWAY_TOKEN；Content-Type application/octet-stream；原始16kHz单声道16bit little-endian PCM，0.5..8秒；X-Voice-Request为1..64安全ASCII，重放相同ID不重复执行。不录到话不执行，不把识别异常当成功。仅此板端接口可从LAN访问，现有首页/历史继续仅回环。
- 成功紧凑正文`ok pause\n`、`ok start\n`或`ok task\n`；失败非200，板端显示FAILED并允许重新点击。不打印令牌。单请求在120秒内完成；录音与识别有限并发。
- `GET /api/voice/state`：仅本机、页面令牌鉴权，最近转写/结果；电脑网页可查看结果。无输入或失效session不恢复旧任务。
- 识别层注入transcriber用于HTTP回归；生产使用本地中文ASR，静音/过低置信度拒绝。转写任务依旧通过已有compiler验证，拒绝现有能力以外任务。暂停及时失效当前看守；设置/继续通过VOICE_CAPTURE回调启动有界电脑摄像头（300秒/60判断）；重复start不重复占用摄像头。
- `watch_voice_gateway <IPv4> <port> <token>`配置RAM内音频网关；`watch_voice [seconds]`命令和触摸共用录音入口；`watch_voice_info`读取状态。配置令牌不回显。无配置/无网络/无麦克风明确失败。
- 保持M33不变，M55音频+网络+显示组合构建和实板读回校验；实际麦克风录音保存并验证非空，但环境静音不等于中文指令识别通过。用保存/合成语音做识别、控制回归，禁止要求真人反复表演。

Wi-Fi到WSL采用Windows只转发音频端点的受鉴权中转；启动器管理服务、相机、桥及退出，不要求用户手工复制令牌。真实连接若被Windows网络策略阻止，记录精确阻塞并保留可运行路径。

## 当前验收（2026-10-21）

已完成host/固件集成和独立复查。最新V5读回一致，实际板卡采集6秒语音经Wi-Fi上传，ASR识别“暂停看守。”并返回DONE pause；使用扬声器回放保存语音，非真人说话验收。保存音频包含环境声的回归通过。实际PC摄像头通过保存的任务/暂停/继续指令验证首帧准备、暂停和重新启动。启动器12秒实板运行退出0、板桥offline；完整111项Python回归（1项Windows专属另测）、JS5、浏览器及原生C/配置检查通过。详见`docs/product-status.md`及`artifacts/board-voice/acceptance.json`。物理触摸点击、屏幕观感、实际用户口音/远场仍未验收。

扩展实板验证现已覆盖任务/暂停/继续三个命令、真实PC相机启停、连接失败恢复，以及120秒板端传输截止后的忙碌释放和再次录音成功。均用保存语音经扬声器回放，无真人参与；视觉模型使用固定响应。详见`docs/autonomous-validation.md`。
