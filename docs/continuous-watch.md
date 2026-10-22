# 持续看守技术测试

目标：用同一程序接受自然语言任务，连续采集电脑实体摄像头，顺序调用 Jev，将状态发送到 Edgi Talk 屏幕；事件首次发生时保存前后帧并请求 Windows 提示音。当前仍由电脑负责采图与联网，板端摄像头不是本阶段的依赖。

## 运行

在本项目的 Windows + WSL 环境：

```sh
python3 -m tools.continuous_watch \
  --task '当有人进入摄像头画面时提醒我。如果画面被遮挡或无法辨认场景，应返回无法确定。' \
  --seconds 300 --interval 5 --max-calls 60
```

默认测试 300 秒，判断结束后等 5 秒再取下一帧，不并发模型请求。通常比较相邻两次采样；上一轮无法确定时，保留原参考帧与新的实际帧继续比较，避免短暂遮挡抹去变化前的画面。参考帧与当前帧相隔超过 30 秒时，退回相邻帧比较。新帧是否更新始终与上次采集检查，不与保留参考帧检查。到达时限或调用上限不再发出新判断；晚到结果不触发事件。模型 HTTP 超时不超过剩余测试预算。测试时限从设备就绪后开始，启动和资源释放另需数秒。图片会发送到已有的 Jev 服务并产生请求费用。

当前环境发现的 Windows Python 路径以及 FFmpeg 路径来自前期实体摄像头探针；摄像头明确选择 `USB 2.0 Camera`，不选择默认编号，以免打开 DroidCam 等虚拟设备。UART 通过 VID/PID 发现 KitProg3。

## 状态与退出

- 首帧及判断过程中，板端显示 `idle`；明确无事件显示 `watching`，事件显示 `event`，证据不足显示 `uncertain`。
- 相同持续事件只保存和提醒一次。`uncertain` 不重新开启事件提醒；明确 `no_event` 后才能再次提醒。
- 相机停止、新帧过旧、模型失败或串口桥停止时结束本轮测试，并尽力发送 `paused`，不解释为“无事件”。
- 独立存活线程每半秒更新租约，串口心跳不依赖模型返回。控制器失去存活租约 3 秒后桥接停止发送；板端随后按自身 5 秒超时变为离线。
- 正常结束发送暂停，释放摄像头，串口桥等待并查询板端离线后关闭串口。相机 watchdog 独立于图像管道读取，先请求退出，3 秒无响应则终止 FFmpeg，避免残留进程占用摄像头。
- `--max-calls` 达上限会以 `call_limit` 提前结束；正常五分钟验收必须是 `stop_reason=duration` 且 `elapsed_seconds` 达到 300。

## 证据

每次运行创建独立的 `artifacts/continuous/<时间>/`，不覆盖旧记录。

- `frames/*.jpg` 和同名 JSON：真实帧和发布时刻。每帧独立索引，避免 Windows 覆盖被 WSL 读者打开的索引文件时出现 PermissionError。
- `rounds.jsonl`：每次判断、输入两帧路径、耗时和返回状态。
- `events/<轮次>/`：首次事件的前后帧和判断；`alert.signal` 触发相机 worker 的 Windows 提示音。保存证据、调用提示音与实际听到提示音是不同证据。
- `summary.json`：实际时长、判断尝试、有效结果、状态计数、事件数及停止原因。尝试次数不等于服务端计费数。
- `serial.txt` / `board-host.log`：实板 ACK、超时和最后离线状态。
- `camera-cleanup.json` / `cleanup.json`：相机释放与子进程退出码。

首次长测记录 `five-minutes/` 在 54.512 秒因共享索引覆盖的 PermissionError 停止，不能算五分钟通过。原失败与源代码快照保留。修复后的完整测试记录为 `five-minutes-v2/`；最终结果以该目录的 summary、cleanup 和串口日志为准。

2026-10-20 实测运行 300.009 秒，53 次有效判断均为 uncertain，1 次晚到结果丢弃；实板最终回报 offline。完整运行结束时摄像头退出码为 1：停止读取管道阻碍 FFmpeg 写完尾部数据，导致超时终止。修复后，独立摄像头定时退出和停止文件退出均以 0 退出；没有重复五分钟付费运行。原始结果与验证范围见 [测试报告](../artifacts/continuous/five-minutes-v2/RESULTS.md)。

单元测试覆盖事件去重、重新提醒、错误暂停、过期结果丢弃、采图跨时限、截止时间与网络超时区别、摄像头退出升级。Windows 文件共享回归需用 Windows Python 执行 `tests/test_camera_publication_windows.py`；Linux 上会明确跳过。

解除遮挡后又运行 300.001 秒、301 帧、51 次判断，摄像头与串口桥均以 0 退出，板卡最终回报 offline。31 次 no_event、20 次 uncertain、0 次最终告警。第 45、46 轮原始选择 event，因 confidence 0.27、0.61 低于现有 0.8 门槛而归为 uncertain；实际帧可见人员出现，存在未提醒证据。持续运行与退出通过，人员进入告警效果尚未通过。见 [解除遮挡测试报告](../artifacts/continuous/uncovered-five-minutes/RESULTS.md)。

遮挡时持续 uncertain 和未遮挡时没有告警，都不能独自证明识别准确率；应对照实际帧和原始判断检查漏报、误报。

漏报修复后，同一段保存的真实画面经真实 Jev 顺序重放，8 次判断触发 1 次事件，持续画面没有重复提醒；两组空画面和一组遮挡控制没有事件误报。另用 3 次真实模型判断重放至实板，收到 event ACK，Windows 相机 worker 记录 ALERT 3，结束后相机和串口桥均以 0 退出。模型、任务、提示词及 confidence 0.8 门槛均未修改；修复只作用于无交互持续采样的参考帧管理，浏览器原型仍使用相邻帧。证据及范围见 [漏报修复报告](../artifacts/decision-fix/RESULTS.md)。

第二类任务“手离开画面”已采到真实现场样本。首次复杂中文描述漏报并于 90.912 秒接口断连，未跑满 120 秒；更简洁的英文任务经保存画面真实 Jev 重放触发实板 event ACK 与 Windows ALERT 2，资源正常释放。中文措辞对照存在漏报与遮挡误报，不能据此宣称任意任务泛化通过。未训练、未更改检测代码。见 [任务切换实验](../artifacts/object-watch/RESULTS.md)。
