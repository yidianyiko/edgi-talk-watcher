> Current integration (2026-10-22): V10 is flashed and verified. `--voice` defaults to the board USB camera; `--camera-source pc` selects the PC fallback. Voice, board frames and event announcements share one authenticated relay and one UART bridge. See [current integration evidence](board-camera-integration.md). Earlier V8/V7 sections below are historical.

> 2026-10-21最新：V8已刷写并verify_bank校验，含语音、事件提醒、屏幕角色及摄像头帧队列修复。摄像头已连接并完成实际采集→Wi-Fi→网关→Jev有界验证，当前证据与有效V7恢复备份见[板端摄像头](board-camera.md)。以下V5/V4为历史记录。

> 2026-10-21：当前已刷入语音V5（1,009,732字节，SHA256 `3fac77def84430a8ea410c1674a821148604ba373941977e810d59df2d7d27b2`），读回contents match。最新实板语音、启动与备份见[语音说明](board-voice.md)和[当前验收](product-status.md)。下文V4为历史映像。新V4整1MiB恢复备份`artifacts/board-voice/before-voice-flash1m.bin`与verify副本双读一致，SHA256 `8efceeef2d155bf739236abf0c74836b2d756036322b49818eeded9c88430fbf`；恢复写bank2偏移0x580000，不写到0x580400。

# 板端状态桥接测试

> 2026-10-20 当前版本：`watch-product-net-20261020-4`，已烧录并读回校验。新增任务、计数、触摸操作请求、Wi-Fi及板端UVC→LAN网关通路；任务协议已实板通过，Wi-Fi扫描成功，摄像头未枚举且网络未关联。完整记录见 `artifacts/product-completion/board/IMPLEMENTATION.md`。以下原始状态桥说明仍有效，但旧映像大小和恢复范围只适用于对应旧版本。
>
> 当前V4映像969632字节，SHA256 `1aeebfe9972aad0091582896bff77250f02a0b71ee1e627b73e5c6f8edfd0e34`。bank2偏移0x580400；擦除sectors22–25。当前有效整段备份为`artifacts/product-completion/board/before-network-initialized1m.bin`，双读一致SHA256 `b7f51be29a3ed4a84c80477105b4e962bbecb0b1dfb12c5111e6749631155c33`，恢复写到bank2偏移0x580000，包含整1MiB四扇区。初始化SMIF前直接dump可能全零，不能用全零文件恢复。保持M33不改。

技术测试范围：PC 判断图像，KitProg3 USB-UART 发送状态，Edgi Talk 的 M55 LCD 显示状态。摄像头不必连接板卡。当前不是独立离线看守设备。

## 固件

源码在 `firmware/status/`，基于官方 BSP `b135be8a28127e276a04b70d27950c3ba07b917a` 的 M55 USB UVC 例程建立独立工程；保留 USB host 能力。M33 引导固件不改动。

```sh
bash tools/build_board_status.sh
```

工具：GNU Arm Embedded GCC 13.2.1、SCons 4.5.2。独立工程在忽略的 `vendor/edgi-talk-bsp/projects/Edgi_Talk_CherryUSB/Edgi_Talk_M55_Watcher/`；可审阅源码保留在 `firmware/status/`。

屏幕显示状态名称、颜色与序号；显示采用 RGB565、实际驱动返回的 pitch。`watch_status <序号> <状态>` 接受 `idle` / `watching` / `event` / `uncertain` / `paused`。有效序号为递增的 uint32，错误命令不改变状态也不刷新心跳。5 秒未收到有效命令，所有在线状态变为 `offline`。重启清零序号；主机每次先读取 `watch_info` 续接。

`WATCH ACK` 在 framebuffer 提交给 LCD 驱动后返回，包含序号、状态、framebuffer FNV-1a。它证明板端代码执行和驱动提交，不证明屏幕实际观感。`watch_info` 包含运行版本、状态、哈希、尺寸与 pitch。

## 主机测试

在 WSL 项目目录运行，脚本自动发现 VID 04B4 / PID F155 的 KitProg3 UART，不使用无关 COM3。

```sh
powershell.exe -NoProfile -File "$(wslpath -w tools/board_status.ps1)" -SelfTest
powershell.exe -NoProfile -File "$(wslpath -w tools/board_status.ps1)" -Status watching -Seconds 30
```

`-SelfTest` 自动检查五种状态、旧序号、未知状态、整数溢出和断连超时。`-Seconds` 在指定时间内发送心跳，结束后设备自动离线。

将一个测试清单里的真实 Jev 判断发送到板卡：

```sh
python3 -m tools.judge_to_board artifacts/board-status/camera/manifest.json --hold-seconds 10
```

这会真实调用一次模型；先连接实板，再发出模型请求。`event` 显示事件，`no_event` 显示看守中，`uncertain` 显示无法确定。模型失败显示暂停并返回失败。保持显示的心跳只用于检查传输，不会重复采图或推理；结束后变为离线。

报告里的 `decision_attempts` 统计判断尝试，不等同于已到达服务端或已计费的请求数；缺少密钥时也可能在网络请求前失败。

## 烧录与恢复证据

当前固件版本 `watch-screen-20261020-1`。Windows OpenOCD 5.19.0.4782，KitProg3 SWD，PSE846GPS2DBZC4A B0。原 M55 8 MiB 原样备份在 `artifacts/board-status/m55-original.bin`，SHA-256 为 `2db6dd4ea0e15561412cc63a949a373d67f8c9bfdff8786256fbc1fb17f892ed`。即将覆盖的前 512 KiB 经第二次独立读取逐字节一致。

本次只擦 QSPI bank 2 的 sector 22–23（从 0x60580000 开始，合计 512 KiB）。BIN 向 bank 2 偏移 **0x580400** 写入；向量表地址 **0x60580400**。前 0x400 字节是原本为 FF 的头部，不把 BIN 错写到 0x580000。OpenOCD `program.log` 记录写入 502184 字节并 `contents match`；随后重启，串口读取到新运行版本。

若恢复此次改动，重置并 halt CM33，以同样的 flash bank 定义仅擦 sector 22–23，将 `m55-original-first512k.bin` 写回 bank 2 偏移 **0x580000**（该文件包含原始头部），verify_bank 一致后 `reset run`。不要使用 erase_all，不要改写 M33。备份文件只保存在本机忽略目录，请保留。

当前实板证据在 `artifacts/board-status/`：`build.log`、`program.log`、`serial-selftest.txt`、`model-to-board.json`。板载摄像头采集、板端联网推理、长期稳定运行仍未验证。
