---
status: hardware_acceptance_pending
blocked_by: [board_uvc_connection, wifi_association, physical_touch_validation]
---
# 板端任务、控制和采集网络能力

重新枚举实板与工具，查已安装官方BSP/原理图/能力，基于真实条件实现任务显示、事件计数、开始暂停/任务切换/历史查看操作协议与屏幕或按键/触摸。调查并实现可行的板端摄像头和网络通路、自测命令。拥有firmware/**、tools/board_status.ps1、tools/build_board_status.sh、新硬件probe脚本和相关C/协议测试。保留状态协议及M33；任何刷写前验证备份和偏移，不改启动固件，不erase_all；若需要刷写先把具体安全步骤报告root协调，root拥有烧录操作。不得打开电脑实体摄像头要求真人动作。真实硬件阻碍要具体，驱动/固件实现与真实验收严格区分。可用不含密钥的串口能力probe。BSP vendor工程可改用于构建，保留可审查源在firmware。见上级spec。

## 已完成的软件与实板边界

V4状态/任务/计数/动作、触摸入口、板端UVC与Wi-Fi、有限采集上传网关循环均已实现并构建。V4烧录读回一致，任务/计数/四动作协议实板通过；V2实板Wi-Fi扫描成功。独立review发现的ID、LAN隔离、互斥模式和任务租约问题已修复回归。尚无板端UVC设备、尚未关联Wi-Fi，物理触摸未验证，不能标记独立设备验收完成。见artifacts/product-completion/board/IMPLEMENTATION.md。
