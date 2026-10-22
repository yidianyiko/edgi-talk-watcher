# 事件语音提醒（2026-10-21）

已加入电脑摄像头统一看守流程；首次实板验收为V6，当前V7保留此能力并增加屏幕角色，见`screen-face.md`。新事件保存成功后，电脑通过现有串口桥要求板卡播放内置中文：

> 注意，看守任务已触发，请查看画面。

网页继续展示具体任务、时间和前后图片，板卡继续显示事件状态和计数。首版是固定提示语，不逐条朗读任务名称；不需要额外TTS服务或密钥。正常启动方式仍为：

```sh
.venv/bin/python -m tools.run_product --voice --seconds 86400
```

每个新提交事件生成随机标识。持续命中、心跳、历史刷新/删除不产生新播报；重启默认暂停且不重放旧提醒。串口忙时保留FIFO队首重试，收到匹配ACK后推进；队列上限100，满时明确报错。ACK表示板卡接受任务，不能当作实际出声证明；板端等待音频独占至多10秒、播放路径至多约7秒，失败输出FAILED，不自动重播已接受的任务。当前仅接入电脑摄像头的统一`/api/observe`事件路径，旧`POST /api/events`导入和未来独立板端摄像头模式不在本次范围。

录音与播放互斥：录音占用期间播报等待，播放期间新录音返回忙；播放后恢复PDM依赖的原TDM时钟。扬声器使用有限池等待、非阻塞入队和静音尾帧，避免官方驱动通用write/close中的无限等待。sound0保持打开，播放故障后需重启板卡恢复音频输出；事件和图片照常保存。

## 实际验证与边界

- 保存的手移除录像帧经真实HTTP应用产生1个事件，真实UART桥收到相同通知标识的ACK，板卡输出PLAY和DONE。视觉模型使用确定性event响应，不能当作新的Jev效果评估。见`artifacts/board-announce/integration/report.json`、`serial.txt`。
- 实板重复同一标识返回duplicate，且只有一次PLAY/DONE；配置就绪后播放期间录音返回NACK。见`artifacts/board-announce/speaker-serial.log`。
- 首轮实板回归暴露播放改变共享时钟导致后续ASR失败。修复后同一保存指令经Windows扬声器→板卡麦克风→Wi-Fi→本地ASR得到“暂停看守。”，DONE pause、busy=0、192000字节、http=ok。红/绿记录分别为`microphone-clock-red.log`和`microphone-clock-fixed.log`，新实板WAV保存在本轮hardware-data/voice下。
- 外部USB摄像头麦克风完成实际录音，但环境声音较强，识别及波形匹配未可靠确认目标提示语。因此**实体扬声器实际出声、音量和清晰度尚未验收**。串口DONE只证明播放调用流程完成。录音原件完整保留，没有把环境语音当作成功。
- `.venv/bin/python -m unittest discover -s tests -p 'test_*.py'`：114项OK、1项平台跳过；Windows Python另测该项1项OK。JS5项通过；构建运行6组原生C检查，含去重/忙/μ-law参考值；独立代码复核未发现剩余应修问题。日志位于`artifacts/board-announce/`。

## 固件与恢复

V6标识`watch-product-voice-20261021-6`，1036908字节，SHA-256 `862b0755ab0ea0bfaf169c14ae6d3f271e63e31fc8ff7672abb266f46cafb73c`。本次归档为`artifacts/board-voice/watcher-voice-v6.bin`；当前`bash tools/build_board_voice.sh`输出V7，检查槽位容量及已链接播报代码。M33未改，M55仍在bank2偏移0x580400、扇区22–25；真实`flash verify_bank`显示contents match，见`flash-clock-fix.log`。

本轮真实读取的V5备份`before-v6-flash1m.bin`已与原V5映像所在区间核对一致，SHA-256 `2b80da0ebc4d2f4f710b62c6f916916b8124673a78f7942417b31f0d5052cd36`。全部早期失败映像和日志保留，不能当作当前通过证据。内置音频为8kHz G.711 μ-law，解码复制为16kHz mono PCM16；原始合成WAV和压缩音频均归档。
