# 项目经验

## 2026-10-20 — hand removal task probe / retro

修改自然语言任务时，同时重放移除、仍在、已无目标和遮挡控制，并保留未用于选择措辞的帧对，以防“成功触发一次”掩盖遮挡误报。手离开实验中，短中文正例 confidence 1.0 却在遮挡上误报，补多项限制后又漏报；简洁英文在本序列对照较好。证据：`artifacts/object-watch/RESULTS.md`。这些是措辞敏感性证据，不能推广为总体中英文能力或泛化准确率；单场景回归帧对也不是独立测试集。

## 2026-10-20 — uncertain reference retention / debug and retro

连续视觉判断暂时 uncertain 时，短期保留变化前参考帧，并独立检查采样新鲜度，以免遮挡帧抹去进入证据。实际空场景→手臂→人员序列，改参考帧后原模型以 confidence 0.97 返回 event；不需要降低置信度门槛。保留必须有时限，本次设为超过 30 秒回到相邻采样。证据：`artifacts/decision-fix/RESULTS.md`。同场景回归、真实 API、实板 ACK、提示音调用和新的现场事件分别报告。

## 2026-10-20 — uncovered scene evidence / retro

评价“没有事件”前，将最终状态、原始选择、confidence 与真实保存帧对照，避免把置信度门槛抑制的告警误报为场景无人。解除遮挡长测第 45、46 轮实际可见人员，但 raw_choice=event 被门槛归为 uncertain；仅看 events=0 曾遗漏这一实景漏报。证据见 `artifacts/continuous/uncovered-five-minutes/RESULTS.md`。持续运行、资源退出与识别效果分别记录。

## 2026-10-20 — continuous watch debug / review / retro

停止摄像头发布后仍需排空 FFmpeg stdout，否则发送 q 后 FFmpeg 无法写完尾部数据，等待退出会超时并触发 kill。300 秒主测试暴露此问题；保留退出码 1 的原始记录，修复后分别用真实定时退出和停止文件退出验证 ffmpeg_exit=0。完整长测与修复后短测的证据范围应分开记录。

跨 Windows/WSL 发布相机帧时，每帧保存独立不可覆盖的元数据索引，避免替换正在被读者打开的文件。首次长测在 54.512 秒出现 PermissionError；Windows 复现用例持有旧索引句柄时覆盖失败（winerror 5），发布新编号索引成功。`tests/test_camera_publication_windows.py` 在实际共享目录回归通过，失败运行保留在 `artifacts/continuous/five-minutes/`。

持续判断的连接心跳独立于推理结束时间，避免 20 秒以内的合法慢请求被当作断线。启动付费请求前检查采图与 payload 准备后的剩余时限，截止后的结果不告警；相机退出 watchdog 独立于阻塞 stdout 读取，并升级到终止 FFmpeg，避免只杀父进程留下设备占用。独立 review 复现了这三个边界，修复后通过对应规则测试与退出检查。

## 2026-10-20 — board bridge review / retro

尝试调用推理函数不等于已发出模型请求。板端桥接的初版报告在缺少密钥、网络调用为零时仍写 `model_calls=1`；独立 review 用空密钥与网络 spy 复现。现改为 `decision_attempts`，明确是判断尝试次数，并以回归测试验证缺少密钥时暂停显示、返回失败、网络调用为零且不报告模型请求数。

## 2026-10-20 — review / retro

外部推理前先校验整批测试的元数据，避免后续案例格式错误导致前面已付费的结果丢失。独立 review 用模拟传输复现：第二组 expected 无效时，第一组已调用、报告尚未落盘。现已将 ID、期望标签、重复 ID 检查移到所有请求之前，新增回归测试覆盖。

## 2026-10-20 — build / review / retro

浏览器的原生全局函数作为依赖传入实例时，使用闭包调用以保留正确的接收者语义。首次浏览器验证在准备状态抛出 `Illegal invocation`，因为 `this.schedule` / `this.cancel` 把 WatchSession 传给 Window 计时器作为 this；Node 的注入测试没有暴露这个差异。现用箭头函数包装默认计时器，并加入模拟浏览器接收者约束的回归测试；随后浏览器全流程通过。未来仍保留真实浏览器检查，单元通过不能代替运行证据。

## 2026-10-20 — user correction / retro

测试阶段的摄像头闭环先由代理直接采集实体摄像头并调用模型，不把浏览器交互交给用户代测。此前把测试阶段推进成界面实现，虚拟摄像头流程通过后让用户自己开启实体摄像头，未满足用户要验证实际采集的目标。WSL 没有 /dev/video* 时继续检查 Windows 宿主机摄像头和可用采集通路，明确区分设备枚举、成功读帧、真实模型判断三层证据。

## 2026-10-20 录像回归与归档完整性（build/review/retro）

用户指出反复真人参与会打断调试。把已有采集固化为本地素材库：保留原帧与时间戳，重建视频注明采样率和时间压缩，日常优先固定素材回归，不重复请求现场动作。审查发现只遍历现存 recording.json 会在丢失整段目录后仍报告校验成功；先以索引固定预期清单，再校验文件及数量。缺失索引素材的回归先报 `AssertionError: ValueError not raised`，修复后通过，实际678帧校验成功。严格标签不匹配（即便没有误报）也保留 failed gate，避免把 uncertain 当全通过。证据：tests/test_recorded_watch.py、artifacts/replay-v1/。

## 2026-10-20 — product completion / debug / review / retro

外部SMIF闪存备份先初始化实际读通路，再检查内容和双读一致性。此次reset/halt后dump_image连续两次得到同一份全零1MiB，哈希一致仍不是有效备份；执行只读flash verify_bank初始化算法后才能读取真实内容。保留全零失败产物；有效双读备份SHA256 b7f51be29a3ed4a84c80477105b4e962bbecb0b1dfb12c5111e6749631155c33，写入前验证字节分布、范围和映像哈希。证据：artifacts/product-completion/board/backup-initialized*.log。

会话生命周期锁覆盖结果有效性检查、事件持久化和状态发布的整体提交，编译和模型网络调用放锁外。暂停返回后不能再提交旧事件；新任务编译结束时再次作废期间启动的旧会话。独立review用barrier复现四处竞态，再由tests/test_web_lifecycle.py回归；仅有模型执行中暂停测试不能覆盖保存阶段的竞态。

新图像传输长测先断言至少一次推理及事件落盘，累计运行验收同时要求模型调用数和事件上限达标。本次首轮HTTP长测用320x240JPEG，低于模型最小边长，造成450次错误恢复而模型调用为零；原报告作废保存在soak/invalid-report.json，不能把运行满五分钟当成有效推理稳定性。

局域网网关监听时只开放令牌验证的板端上传路由，普通页面、事件及任务接口保持本机访问。独立review发现仅保护上传令牌、同时把首页暴露到LAN，会让普通客户端从首页取得网页操作令牌。新增远端IP访问回归。板端上传任务ID保留数据库整数ID，不能只对显示桥哈希后用于网关校验；对应跨通路回归已补。

## 2026-10-20 — board local lease / debug and retro

板端本地操作（新任务、暂停、切换）与 UART 状态更新共用状态租约转换函数，保留主机序号并同时刷新 updated_ms。V3 实板在开机较久后执行 watch_task，ACK 后立刻 WATCH TIMEOUT offline，因为只改了状态而沿用旧时间。新增 C 回归从100000ms起暂停，检查4999ms内不超时、5000ms时超时，并验证原序号不变；源码统一使用 watch_pause。证据：artifacts/product-completion/board/v3-real-protocol.txt、lease-red.txt、lease-green.txt。仅检查字段合法和编译通过不能覆盖经过较长开机时间的本地交互。

上述HTTP长测修正后运行300.79秒，437次模拟推理、922次HTTP请求、6次预期故障恢复，达到并保持100事件上限，全部显式断言通过；首轮作废记录仍保留。

## 2026-10-20 — PC relay / build / review / retro

控制轮询把合法的JSON null视为空动作，并用“首轮无动作→随后暂停在途判断”验证监听持续存活。PC中转实际HTTP曾出现模型事件已保存但控制线程None.get退出；只有Mock返回字典的单元测试未覆盖真实无请求契约。新增用例先复现失败、修复后通过，再用真实HTTP保存画面复测确认无线程异常。证据：tests/test_pc_camera_relay.py、artifacts/pc-relay-validation/recorded-null-fixed/。

## 2026-10-21：板卡语音组合驱动（build/debug/review/retro）

组合驱动时沿实际注册调用链核对启动依赖：本次官方 `rt_audio_register` 立即调用 `rt_device_init`，即使不播放也会进入 ES8388 初始化；仅启用 AUDIO_PLAY 而未启用其 I2C0 导致实板停在 `rt_assert_handler`。源码复查未覆盖这个传递依赖，flash verify成功也不能证明启动。先用SWD PC及官方驱动源码确认原因，再补官方硬件I2C0配置，并把依赖检查加入构建；保留首烧失败映像。证据：`artifacts/board-voice/inspect-boot.log`、`config-red.log`、`build.log`与`tests/check_board_voice_config.py`。

录音截止要沿真正设备read路径核对：RT-Thread音频使用 `drivers/audio/audio_pipe.c`，不是普通IPC pipe；默认 BLOCK_RD 会在空数据无限等待。录制时临时清除阻塞标志、保留写策略、所有退出恢复，并用空输入/部分输入截止测试和故障变体验证。证据：`artifacts/board-voice/capture-blocking-red.log`、`tests/test_voice_capture.c`。

Flash备份使用已验证的 `flash read_bank`，再检查字节分布、映像所在区间以及双读一致。本次即便`flash verify_bank`成功，CM33 `dump_image`仍返回全零，原先“verify即初始化原始读取路径”的推断不足。两次read_bank得到非零、与当前V4映像一致的1MiB备份；全部失败产物仍保留，不能用于恢复。证据：`artifacts/board-voice/backup-verified.json`、`backup-flash-v4.log`。

异步准备完成与请求取消须原子处理失败分支：Future的done检查和set_result之间可被取消；该异常若从finally逃逸会跳过排队相机启动。捕获InvalidStateError以继续资源释放，保存确定性交错回归。证据：`artifacts/board-voice/capture-cancel-race-red.log`、`capture-cancel-race-green.log`。

语音中转的租约从子进程启动后计时，并在耗时Wi-Fi配置之后刷新父心跳。首版在配置前创建alive文件，配置耗时超过4秒后，子进程启动半秒即退出，早于父进程第一轮心跳；表现为板卡录音成功却连接不到中转。子进程回归现覆盖过期30秒的旧alive文件、就绪后首轮心跳宽限与无父心跳自动退出。证据：`artifacts/board-voice/hardware-smoke-connectivity.log`、`proxy-startup-lease-red.log`、`proxy-startup-lease-green.log`。

识别验收包含设备真实采集的前后环境声：仅使用短合成WAV时识别正确，不代表6秒板卡录音正确。此次完整录音未做VAD时重复了提示词中的“继续看守”，严格命令解析拒绝了它，没有误执行；相同已存录音启用语音片段检测后正确识别“暂停看守”。保留该192000字节PCM为`testdata/voice/board-pause.wav`，可选实际ASR回归同时检查三条合成指令和无语音噪声，避免后续继续依靠真人。证据：`artifacts/board-voice/board-asr-vad-red.log`、`board-asr-vad-green.log`。

## 2026-10-21：故障验证只读取操作后的最终状态（review / retro）

语音超时脚本同时打印操作前后VOICE INFO，最初用整段输出包含busy=0作为通过条件；独立review用“开始busy=0、结束busy=1”的转录复现假通过。现按最后一条VOICE INFO检查FAILED且busy=0，并在新运行前清除旧的成功报告和故障服务就绪/接收标记，避免把旧证据算入当前验证。证据：`artifacts/voice-autonomous/timeout.py`与`verify.py`。这是测试判断的修正，不能据此声称产品曾出现忙碌不释放。

## 2026-10-21：事件提醒的排队、共享时钟与实体证据（shape/build/debug/review/retro）

新事件逐条排队直到板卡确认接受，不能用单一最新ID覆盖忙时尚未接受的提醒。独立review复现A收到busy后被B覆盖；FIFO红/绿测试和匹配ACK文件现覆盖该情况。证据：`artifacts/board-announce/queue-red.log`、`tests/test_announcement.py`。

音频功能回归覆盖“播放→真实录音→识别执行”，因为本BSP的PDM依赖TDM启动时钟。单声道播放配置改变分频后，原录音长度仍可能达标但识别失败；播放完成/失败均恢复启动stereo16k，下一次播放再配置mono。实际相同保存指令先HTTP422，修复后DONE pause/httpok，见`microphone-clock-red.log`和`microphone-clock-fixed.log`。保留有限等待和录放互斥，不使用驱动无限等待的通用close。

构建检查已链接的FinSH命令、音频数据和音频所有权符号，因为条件宏必须在读取rtconfig后判断。本轮初版未包含rtthread即判断宏，使整个announce实现被静默编译掉；现构建脚本检查ELF且约束原槽位大小。实体扬声器验收需录音识别或可解释的信号证据，PLAY/DONE只能证明调用流程；本轮环境录音无法可靠辨认提示语，明确保留未验收结论。证据：`build-final-verified.log`、`speaker-serial.log`、`docs/event-announcement.md`。

## 2026-10-21：摄像头空帧队列与异步启动（debug/build/review/retro）

验证取帧等待是否真的等待已完成帧，因为BSP的接收信号量错误地按空闲缓冲区数量初始化。V7第一次dequeue立刻返回空，清理尚未启动完成的UVC流导致tshell HardFault；官方预览循环可持续出帧。现用实际vendor队列和OSAL配合信号量桩验证空队列等待、生产者提交后才可读，持久补丁将初始值改为0。红/绿证据与V8连续两次单帧采集、两帧Wi-Fi上传和一次真实Jev见`artifacts/board-camera/`。本次修复不能替代拔线、未成功打开视频流等其他清理路径的验收。

## 2026-10-22: repeat camera sessions and completion claims

- Skill: debug/build/review. A successful first USB capture did not establish reusable sessions: two fresh actual-hardware runs succeeded once and failed reopening with IO -12. Verify start → stop → start against the flashed image before describing the daily workflow as passed. Preserve the failing UART transcript and original frames; use the supported USB-host restart as explicit recovery instead of claiming a proprietary driver fix.
- Report cycle completion only after observing the final response and stop acknowledgment. An interim update incorrectly described two successful cycles before the second response arrived; the correction and retained failure led to the V9 repeat-session test.
- Preserve valid received frames before model evaluation so failed-model and superseded results can be debugged offline without repeating a physical scene. Regression `tests/test_board_camera_admission.py` observed one archived frame instead of two, then passed after the archive moved before inference.


### USB shutdown acceptance (2026-10-22)

- V9 passed seven starts but hard-faulted on the final stream stop. A first-frame response or several successful sessions does not establish repeated shutdown reliability.
- Preserve the matching ELF, both thread and exception stacks, USB channel registers and UART trace before resetting a faulted board. Here those showed a stale channel-halted IRQ after the proprietary cancellation routine cleared its URB pointer, separating the actual fault from an initially plausible freed-buffer callback race.
- Failure reports must refresh persisted event counts in cleanup; a report last saved before a failed shutdown can lag the database.
