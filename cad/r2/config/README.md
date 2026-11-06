# R2 候選設定

目前 `build.ps1 -Physics` 同時套用 `drag_candidate.json` 與 `native_friction_trial.json`。前者是未實測的軸阻力與馬達預算，後者是原生碰撞與關節摩擦的數值求解設定。固定的驗收結果請讀取 `../review_native/acceptance.json`。

- `drag_candidate.json`：分鐘 5 mN·m、小時 20 mN·m，單一輸入扭矩上限 50 mN·m。毛氈預壓及實際馬達尚待量測。
- `native_friction_trial.json`：本輪選用；接觸時間常數 0.0006 s，關節摩擦 0.0002 s／阻抗 0.999。時間步長必須不大於 0.0001 s。
- `native_collision_trial.json`：只切換原生碰撞的早期診斷，保留原有摩擦正則化；曾在連續分鐘步進出現閒置偏移。
- `solver_candidate.json`：保留的舊版硬接觸診斷；其試驗失敗，未選為預設。來源快照保留於對應運算紀錄。

這些設定沒有代表列印塑料彈性、毛氈壓縮或真實摩擦材料定律；變更設定後須重新執行逐步驗收與時間步長比較。
