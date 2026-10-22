# 无真人参与的实板回归

2026-10-21使用已保存的合成语音，由Windows默认扬声器播放，让Edgi Talk实际麦克风录音；通过实际Wi-Fi、Windows音频中转及本地中文ASR执行命令。不需要用户说话或操作浏览器。

## 已取得的证据

`artifacts/voice-autonomous/report.json`记录6次操作：设置任务、暂停、继续、暂停、服务地址不可用、恢复地址后暂停。全部符合预期，串口最后一条VOICE INFO均busy=0；成功的5段录音均为6秒、16kHz、单声道PCM16，保留原始WAV与SHA-256。设置任务和继续各启动一次真实电脑摄像头，两次均取得画面并正常退出。

这一轮使用已缓存的“有人进入画面时提醒我”计划、固定no_event视觉响应。它验证语音和相机控制，不作为新任务编译或真实Jev判断的证据。相机画面和退出报告在`artifacts/voice-autonomous/camera/`。

测试脚本及原始日志均在`artifacts/voice-autonomous/`：

- `run.py`：完整命令循环与服务连接失败恢复。
- `timeout.py`、`stalled_server.py`、`timeout-smoke.ps1`：独立认证测试服务收到音频后不回复，检验板卡真实传输截止与恢复。结果以`timeout-report.json`、`timeout-serial.log`和`timeout-recovery.log`为准。
- `verify.py`：复核最终busy状态、转写动作、音频格式/校验和与相机释放；超时报告存在时一并检查。

这些实板脚本会占用UART并临时改板卡RAM中的音频网关地址。运行前先正常停止`tools.run_product`，全部测试后重新启动语音模式，恢复实际产品端口；不要和产品服务争抢串口。再次测试前保留整份旧目录，日志不能混用成新一轮通过证据。

## 当前软件与素材复核

本轮Python111项通过，WSL跳过1项Windows文件共享语义，该项另用Windows Python执行通过；JavaScript5项通过。`tools.archive_recordings --verify`确认678张原始帧、元数据及视频校验和完整。日志保存在同一证据目录。

物理SPEAK触摸点击、实体屏幕观感、不同用户口音/远场识别率及尚未接入的板端摄像头仍未验收。当前保留电脑摄像头，按用户决定等待转接头。


超时扩展实测也通过：测试服务实际收到192000字节音频后不响应，板卡在传输120秒截止处返回`stage=read-wait err=-2`，最终FAILED且busy=0。整条串口测试含准备和录音共135.17秒；恢复网关地址后再次实际录音，ASR暂停命令成功。证据`artifacts/voice-autonomous/timeout-report.json`、`timeout-serial.log`、`timeout-recovery.log`。未断开Windows网络；故障注入是独立服务不响应。

测试后已恢复`tools.run_product --voice --seconds 86400`，本机网页HTTP200，语音中转ready，板桥BOARD READY并持续paused ACK；当前暂停待命。运行证据`artifacts/voice-autonomous/live-ready.json`。24小时是进程运行上限，不代表已完成24小时长测。
