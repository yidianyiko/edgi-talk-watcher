# 屏幕角色（2026-10-21）

V7在Edgi Talk屏幕中央增加两只原生RGB565眼睛。观察时左右看并眨眼，暂停眯眼，离线灰色，事件琥珀色，不确定不对称；录音睁大，识别用紫色思考表情。保留任务、计数、状态、SPEAK及底部操作。实现见`firmware/status/face.c`、`main.c`，规范见`specs/screen-face.md`。

本轮归档固件`watch-product-voice-20261021-7`，1038516字节，SHA-256 `b15116fa9793dd0839622fb64c782dd7bbe7b3a351643985b0bf8d2e3ab6c4af`；原四扇区槽位尚余9036字节。当时构建命令`bash tools/build_board_voice.sh`，归档产物`artifacts/board-voice/watcher-voice-v7.bin`。刷写bank2偏移0x580400，M33未改；实际verify_bank返回contents match，见`artifacts/board-face/flash.log`。

刷写前的1MiB V6备份已验证，与旧V6产物在+0x400处一致；`before-v7-flash1m.bin` SHA-256 `572d2ead589a0f7267baf57b62447283fb05c48a1f868b864092a13ccc5c7210`。恢复方式沿用`board-status.md`，使用该有效备份，保留所有失败记录。

本轮验证：114项Python运行OK（Linux跳过1项Windows专属项，该项另在Windows执行OK）、JS5项、7组原生C测试通过。`test_face`覆盖状态映射、眨眼、视线、八种表情和绘图边界；独立review无发现。

`artifacts/board-face/expressions.png`是与固件共用C渲染器的表情预览。实际板卡framebuffer：`screen.png`为观察状态读回，读取期间动画重绘产生局部读回撕裂；`screen-still.png`为暂停M55后完整读回的离线状态，读取后已resume。这些不是实体屏幕照片，实体触摸与肉眼观感仍未验收。后续尝试重新初始化调试器未成功获取设备，未覆盖已有通过证据。

实际录音回归先失败HTTP422，识别文本不匹配有效命令，没有执行动作；同一保存音频再次经Windows扬声器→板卡实际麦克风→Wi-Fi→本地ASR，识别“暂停看守。”并返回DONE action=pause、busy=0、http=ok。分别见`microphone-regression.log`与`microphone-retry.log`，两份实板WAV均保留在`hardware-data/voice/`。没有修改ASR逻辑；重复成功不能证明不同噪声条件下的识别稳定性。串口测试退出0仅代表操作结束，本结论以最终VOICE INFO及服务端voice_state为准。

实体扬声器提示语的实际发声/清晰度仍沿用`event-announcement.md`的待验边界；本轮没有重新声称已验收。

当前V8保留全部屏幕角色能力，构建脚本现输出V8，见`board-camera.md`。
