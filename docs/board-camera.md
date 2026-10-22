> Current integration (2026-10-22): V10 is flashed and verified. `--voice` defaults to the board USB camera; `--camera-source pc` selects the PC fallback. Voice, board frames and event announcements share one authenticated relay and one UART bridge. See [current integration evidence](board-camera-integration.md). Earlier V8/V7 sections below are historical.

# 板端摄像头（2026-10-21）

摄像头接入板卡USB host后，真实枚举为video_ctrl/video_streaming，480M；支持MJPEG和YUYV，包括320×240。BSP原有视频命令实际输出153600字节YUYV帧，约29–30fps。`reference-start.log`中的帧率是原例程预览能力，不是当前看守每秒调用模型次数。

## 当前实板结果

V8 `watch-product-voice-20261021-8`，1038516字节，SHA-256 `0f40b09e7fcdf556cb8df4466867ecfb9df89c49a8efc20e5aef471d56a71a3d`。构建`bash tools/build_board_voice.sh`。bank2偏移0x580400、扇区22–25，M33保持；实际verify_bank为contents match，见`artifacts/board-camera/flash-v8.log`。

刷写前的V7整1MiB备份`artifacts/board-camera/before-v8-flash1m.bin`经过读回校验，+0x400区间与归档V7一致，SHA-256 `46a32c9ac59cf869f944232eb036cf11e7ef639d2c3df174ec17f71b5a881b51`。恢复遵循`board-status.md`，整备份应写bank2偏移0x580000。

- 连续两次`watch_capture`均ACK，153600字节，320×240 YUYV；随后watch_info/watch_probe正常。见`capture-v8.log`。
- 真实板卡USB采集→板卡Wi-Fi→Windows受鉴权探测中转→WSL网关→Jev：实际上传2帧，1次真实模型调用，返回uncertain，0事件。保存的“手消失”任务仅为已有测试计划；未要求真人动作，不据此评价事件准确率。见`gateway-report.json`、`gateway-serial.log`。
- 原始帧`board-frame-1.yuyv`、`board-frame-2.yuyv`各153600字节，报告记录SHA-256和接收时间。JPEG为网关标准转换/640×480放大结果；`preview.mp4`按每张5秒重建无声预览，不是连续全帧率录像。
- 软件回归114项Python OK（Linux跳过1项，该项另用Windows Python运行OK），JS5项、8组原生C检查通过；独立review无具体发现。

采集结束后再次通过实际板卡麦克风录音→Wi-Fi→本地ASR识别“暂停看守。”，DONE action=pause、busy=0、http=ok；见`microphone-regression.log`及留档WAV。这不是不同噪声/用户条件下的稳定性评估。

## 根因与回归

V7首次采集立即NACK，随后usbh_video_stream_stop在usbh_kill_urb读取尚未初始化的URB时HardFault，BFAR=0x23233227。重启后重复出现，见`camera-probe-after-reset.log`。官方视频预览持续取帧成功，排除格式不支持。

BSP `chry_mempool_osal_sem_create(max_count)`把空接收队列信号量初始化为缓冲区数量。第一次dequeue因此没有等到真实帧就返回空，清理与异步视频启动交错。修正初始信号量为0；实际vendor池/OSAL配合原生信号量边界桩的测试，修正前在`waited==50`失败，修正后验证空队列等待、已完成帧才唤醒。见`tests/test_camera_pool.c`和`pool-red.log`/`pool-green.log`。

补丁持久保存在`firmware/patches/camera-empty-queue.patch`，构建只接受可应用或恰好已应用的补丁状态；拒绝冲突源文件。修正后实际重复采集与两帧上传均完成。预编译UVC流库的其他启动失败/拔线清理情况没有覆盖，不能把本修复当作所有USB故障恢复已验收。

## 模式边界

本次通过`artifacts/board-camera/gateway-smoke.py`、`frame-proxy.py`和`gateway-serial.ps1`完成有界实板诊断，测试服务/中转随后关闭。Windows中转只允许受鉴权的固定长度board observe上传，不开放网页和通用代理；测试令牌不回显。

日常`tools.run_product --voice`仍连接原PC CameraSupervisor。板端已有watch_run有界通路，但语音开始/暂停与日常启动器自动选用板端相机尚未接入；事件播报也沿用`event-announcement.md`对PC统一事件路径的边界。本次不能称为日常产品已全面迁移到板端相机。模型与持久记录仍在电脑上，并非全离线独立设备。

收尾恢复原日常语音服务到暂停态：HTTP200、板卡状态桥和语音中转均ready，V8版本；时间/PID/日志路径见`artifacts/board-camera/live-ready.json`。测试网关/相机中转已关闭。
