# 电脑摄像头闭环验证

2026-10-20。本次实现位于 `watcher/`，入口 `python3 -m watcher.app`，仅监听 `127.0.0.1:8765`。当前目录没有 Git 仓库，未创建提交。

## 已验证

- `python3 -m unittest discover -s tests -v`：13 项通过，包括 7 项原探针测试和 6 项 HTTP 边界测试。
- `node --test tests/watcher_state.test.mjs`：4 项通过，覆盖暂停后忽略旧响应、事件锁存、网络失败暂停及浏览器原生计时器的接收者问题。
- `node --check watcher/static/app.js`：通过。
- 浏览器使用已安装的 Playwright 与 Chromium 155，虚拟摄像头运行。通过首页输入任务 → 开启摄像头 → 开始 → 事件截图 → 持续事件不重复提醒 → 暂停后没有新请求 → 关闭摄像头。控制流程中的事件结果使用拦截响应，不代表模型识别了虚拟画面的事件。
- 同一浏览器移除拦截后，经页面 → 本机 Flask → 真实 `jev-1.14.0` 调用成功。第一次结果为无法确定，耗时 0.40 秒、confidence=0.28。正式保存的测试脚本再次调用成功，结果为无法确定、耗时 0.41 秒、confidence=0.34。共两次真实调用；第二次结果记录在 `artifacts/watcher/browser-report.json`。
- 浏览器无 JavaScript 异常；390px 移动端布局无横向溢出。
- 独立 review 没有剩余 blocker 或 should-fix；计时器问题修复后经回归及独立复查通过。

## 浏览器检查复跑

先启动服务，然后执行（需要已安装 Playwright 及其 Chromium，或提供本机可执行文件路径）：

```sh
node tests/browser_watcher.cjs
```

可以使用 `PLAYWRIGHT_MODULE` 指定已安装的 Playwright 模块，使用 `CHROMIUM_PATH` 指定 Chromium 可执行文件。默认只测试控制流程，不发真实模型请求。显式设置 `LIVE_JEV=1` 会额外经虚拟摄像头发一次真实付费请求。

本次实际使用：

```sh
PLAYWRIGHT_MODULE=/home/ydyk/.npm-global/lib/node_modules/@playwright/mcp/node_modules/playwright CHROMIUM_PATH=/snap/chromium/current/usr/lib/chromium-browser/chrome LIVE_JEV=1 node tests/browser_watcher.cjs
```

截图及最终报告在 `artifacts/watcher/`。初始界面 `initial.png`，模拟事件流程 `event.png`，手机布局 `mobile.png`。

## 尚未验证

Linux 没有 `/dev/video*` 设备；后续已通过 Windows 宿主机 DirectShow 按名称读取 USB 2.0 Camera，完成真实摄像头遮挡测试。用户确认相机被主动遮挡，Jev 原始结果为 uncertain、confidence=1.0，耗时 0.512 秒。详见 `artifacts/physical-camera/RESULTS.md`。解除遮挡后的真实桌面事件识别尚未验收，Edgi Talk 板卡未接入。提示音已实现，未验证实体扬声器听感。采样存在漏检时间窗，模型仍会误判；切到后台会暂停。
