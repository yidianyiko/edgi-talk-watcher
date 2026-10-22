---
status: open
blocked_by: []
---
# 统一任务、持久事件与可恢复网页

网页新任务只编译一次，显示进度/拒绝原因并持久缓存。事件及前后图本地持久存储，支持查询清理和100条保留；刷新/重启后恢复任务但不自动开摄像头。接入可用共享引擎语义、任务更换/暂停/后台/断网恢复无旧结果。完善测试与真实浏览器模拟录像验收。拥有 watcher/app.py, watcher/task_plan.py, watcher/store.py（可新增）, watcher/static/*, watcher/templates/*, tests/test_watcher.py及新web/store测试, tests/watcher_state.test.mjs, tests/browser_watcher.cjs。不改engine.py/continuous_watch.py/replay_session.py/firmware。引擎接口见spec；需要确认接口先与001交流。对API注入测试不要意外调用真实编译器。见上级spec。
