# 已保存的 FC-R1 物理回放

這是 2026-11-04 完成的 1.6 秒 MuJoCo 3.17.0 探索性運算。

- [整機影片](physics.mp4) · [翻片近看](front.mp4) · [傳動背面](rear.mp4)
- [操作及限制](../../PHYSICS_VIEW.md) · [數值結果](../../reports/physics_assessment.json)
- states.npz 保存積分結果；紅點取自 contact_points.json.gz。
- model/ 包含可重新編譯的物理模型與自有 CAD 視覺網格，不包含原作者模型。
- source/ 保存運算當時的程式，provenance/ 保存來源設定與影片渲染程式。
- comparisons/ 保存相同模型的無重力及較小時間步長對照；共用主模型。
- 省略 .mjb 與 compiled.json 引擎快取，首次開啟時自動從 XML/STL 建立。

互動視窗尚待使用者自行確認；尚未完成實測校準、定位保持與單片放行驗收。
資料是 concept_only，physics_verified 與 manufacturing_ready 均為 false。
