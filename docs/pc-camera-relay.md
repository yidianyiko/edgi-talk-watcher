# 电脑摄像头临时中转

摄像头继续插在电脑上。当前通路：Windows具名`USB 2.0 Camera` → PC中转 → 本机看守服务 → Jev → SQLite事件/前后图 → USB-UART板卡显示。模型和记录服务与后续板端采集共用；转接头到货后切换采集来源，不必重做任务和历史逻辑。

终端一启动服务，等看到`Watcher http://... board=True`：

```sh
python3 -m tools.run_product --board
```

终端二启动有界采集：

```sh
python3 -m tools.pc_camera_relay --task '当画面中原本可见的手消失时提醒我。' --seconds 300 --interval 5 --max-calls 60
```

省略`--task`使用服务中上次保存的任务。采集器保留帧和时间戳到`artifacts/pc-relay/`，事件和前后证据保存在服务数据目录。采集间隔从上一次判断结束后计时；只有新鲜帧才提交。达到时限、调用上限或错误即暂停并释放摄像头，不自动重试。板卡pause/next请求无需浏览器即可停止中转并作废在途结果；CLI重新开始需再次运行命令，start/history不是CLI恢复或浏览历史命令。网页仍可用于查看历史。

后续回归默认复用录像，不反复打开真人摄像头：

```sh
python3 -m tools.pc_camera_relay --recording testdata/recordings/hand-removal --seconds 30 --interval 10 --max-calls 1
```

此命令读取有校验的原始帧与时间戳，不打开摄像头；仍会调用真实模型，受max-calls限制。

## Wi-Fi连接

在项目私有`.env.local`追加，保留原来的JEV_TOKEN：

```dotenv
WIFI_SSID="你的Wi-Fi名称"
WIFI_PASSWORD="你的Wi-Fi密码"
```

在没有其他程序占用KitProg3串口时运行：

```sh
powershell.exe -NoProfile -File "$(wslpath -w tools/connect_board_wifi.ps1)"
```

脚本读取配置后经当前网络固件官方`wifi join`命令连接，串口命令及回显包含密码，因此一律不输出也不写日志；只有确认指定SSID连接且IP ready才报告成功。凭据保留在电脑私有文件，不写入本次固件；板卡重启后可再次运行。`-ValidateOnly`只校验配置且不访问串口。当前FinSH命令长度80字节；无法安全表示或超长配置会在打开串口前明确拒绝，由实现侧扩展固件后再连接。

已按用户授权从Windows保存的Wi-Fi配置读取凭据，写入权限0600的私有`.env.local`，连接实际板卡成功；再次独立读取确认connected=1、ready=1、IP为[private DHCP address]（DHCP地址后续可能改变）。密码未打印或写入测试日志，临时导出配置已删除。当前电脑摄像头+UART中转无需板卡Wi-Fi即可使用。

## 验证（2026-10-20）

- 电脑实体摄像头：6帧，2次observe（首帧准备、1次真实Jev判断uncertain），摄像头及FFmpeg退出0、released=true；没有要求真人动作。`artifacts/pc-relay-validation/live-ready/`。
- 增加控制监听后实际HTTP录像回归：2次observe、1次真实Jev事件、证据入库，正常暂停；`recorded-null-fixed/summary.json`及`recorded-server.log`。中转测试服务连接实际板卡串口；结果显示独立于摄像头插接位置。该次使用保存画面，不能称为新现场事件。
- 首次中转早于服务就绪而URLError，保留live/summary.json；随后等待服务就绪后实体采集通过。
- 实际HTTP发现无控制请求返回JSON null，初版监听线程退出；增强回归先失败，再修复为空动作继续轮询。不能把之前事件成功误当控制监听已成功。
- 4项中转测试、3项实际PowerShell配置测试（临时虚构凭据）通过；这些配置测试未访问串口；真实Wi-Fi另已按下项验证。独立review及修复后复审无剩余should-fix。

- 最终主机回归：82 tests，OK（Linux跳过1项Windows共享语义测试）；`artifacts/pc-relay-validation/final-host-tests.log`。
- 实板Wi-Fi：Windows已有Wi-Fi配置安全读取，指定SSID关联成功并取得DHCP地址；独立复查connected/ready均true，IP[private DHCP address]，证据`artifacts/pc-relay-validation/wifi-ready.json`。不等于板端摄像头无线上传已验收。
