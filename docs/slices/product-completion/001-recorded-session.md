---
status: done
blocked_by: []
---
# 整段录像复用真实看守逻辑

用户可用已存录像从头到尾自动测试，不需要真人。实现共享状态机、按原始时间的完整回放入口、零联网模型响应重放；去重、uncertain参考保留、截止、错误、调用上限可测试。三段完整录像真实模型验收并保留报告，默认10秒采样，每段最多40次调用；不把跳过尾部称完整。允许在数据支持时修复判定，但模型阈值不要随意降低，不写目标专用规则。拥有 watcher/engine.py, tools/replay_session.py, tools/continuous_watch.py, engine/replay相关新tests。不改 app.py、前端、task_plan.py、firmware。见上级spec。


软件实现完成，证据见 `artifacts/product-completion/recorded/RESULTS.md`。三段整段时间覆盖真实模型共67次调用，全部包含尾帧；零联网重放逐轮一致。手消失后持续空场景8轮uncertain，严格状态分类仍有限制，不能称长期可靠性通过。独立review由主任务安排。
