# FC-R1：全新單馬達雙棘輪翻頁時鐘

2026-11-04 依使用者最新指示改為完整重新設計。使用 text-to-cad 0.7.17、
build123d 0.11.1／Open CASCADE 建立可修改參數、可自動重建的精確實體。
工程主檔是 `src/*.py` 與 `config/parameters.yaml`；STEP 是可交換工程模型。
本機未安裝 FreeCAD，因此沒有把網格或 STEP 冒稱成 FreeCAD 原生參數檔。

**狀態：concept_only，工程原型；不是完成動態驗證的製造發行版。**

新設計不匯入原作者的 3MF、STL 或其他幾何，也不使用其量測尺寸作參數。
使用者之前提供的檔案保留於 Git 忽略的 `source/original/`，不屬於本模型依賴，
不進入原型包；先前的量測報告也不作為新設計的尺寸來源。

## 模型內容

- 單一輸入軸，兩個相反接合方向的內棘齒環、獨立棘爪、金屬銷與彈簧。
- 分支路 40→20→40 齒，兩次外嚙合，輸出與離合器同向。
- 時支路 60→60 齒，一次外嚙合，輸出與離合器反向。
- 模數 1.8 mm、20° 壓力角、實際漸開線與齒根圓角；齒比均為 1:1。
- 分鼓 60 片、6° 孔距；時鼓 24 片、15° 孔距。兩支輸出軸獨立支承。
- 從 +Y 正面觀看，時輪在左、分輪在右，字形按此觀察方向配置。
- 84 片實體翻片及銷；自繪七段數字，A 面為本值上半，B 面為下一值下半。
- 60／24 槽獨立定位盤、滾輪、樞轉臂、彈簧與預壓調整件。
- 順向手動旋鈕、可調翻片釋放支架、感測安裝架、磁鐵帽與側護板。
- 24／36／48 齒棘輪試片、反向試片、8 mm 配合階梯與單離合器負載治具。

**整機翻片呈徑向展開檢查姿態；釋放指退到外側。** 這方便數量、間隙及零件檢查，
不表示實際重力平衡、顯示姿態或翻片時序已解算。另提供由 MuJoCo 積分與接觸力解算的重力檢視，詳見 `PHYSICS_VIEW.md`。

## 重建

在專案根目錄 `D:\Project\Flip-Clock` 的 PowerShell 執行：

```powershell
.\cad\run.ps1 doctor
.\cad\run.ps1 build-cad --model all
.\cad\run.ps1 check-geometry --all
.\cad\run.ps1 export-parts
.\cad\run.ps1 drawings
.\cad\run.ps1 render
.\cad\run.ps1 viewer
.\cad\run.ps1 package --prototype
```

`run.ps1` 使用本專案 `.build/cad/` 中的 uv、Python 套件快取、CAD 快取與瀏覽器，
不改全域 Python。日常重建離線執行。第一次在其他電腦建立環境時先執行：

```powershell
.\cad\setup.ps1
```

`initialize_design.py` 是最初建檔工具，**不要在調整參數後再次執行**，以免回復預設值。
參數檔以 JSON 語法保存，亦是有效 YAML；可用一般文字編輯器修改 `value`。
每個參數附單位、需求／提案狀態、來源、不確定度與量測日期；未知資料使用 null。

## 交付目錄

- `STEP/assembly.step`：完整工程組裝；其他 STEP 為可獨立查看的子系統。
- `STEP/parts/`、`STL/prototype/`：由已保存組裝匯出的工程原型分件。
- `reports/geometry_check.json`：實際讀回 STEP 的檢查結果及未檢查項。
- `reports/parts_catalog.json`、`reports/bom.csv`：分件、材料估計、數量與列印方向。
- `reports/mass_properties_SI.json`：以 CAD 實心密度估算的質量、重心與慣量；不是實測。
- `reports/verification.json`：幾何、動態、硬體、耐久分開記錄。
- `tmp/review/`：已渲染的模型視圖，僅供幾何審閱。
- `prototype_FC-R1.zip`：明確標示原型的本地交付包；不包含原作者檔案。
- `review/physics/`：GitHub 可直接查看的影片、已保存物理軌跡及可攜式模型；操作見 [PHYSICS_VIEW.md](PHYSICS_VIEW.md)。

GitHub 保存參數化來源與這次物理回放；STEP、列印 STL、PDF 與打包 ZIP 是本地產物，依上方指令重建。
原生互動視窗尚待使用者自行檢查，影片與物理解算紀錄不代表桌面操作已驗證。

## 驗證邊界

幾何檢查只對報告中列出的項目判定 PASS。連續全轉角碰撞、重力落片、棘爪接觸、
定位扭矩、有限馬達能力、塑料強度、疲勞與實機耐久均須另有證據。
`export-physics` 建立 MuJoCo 接觸模型；`simulate` 執行探索性物理運算並保存軌跡、接觸力與運算設定。
`physics.ps1 view` 開啟可互動的物理視窗。馬達、彈簧及摩擦尚未實測校準，這些運算不等於完成物理驗收。
未帶 `--prototype` 的打包拒絕製造版發行。

馬達與感測器只以有標示的採購件包絡表示；實際軸扁位、孔位、感測間隙及料號仍待核對。
本資料夾的機構需求與現有 ESP 韌體不同；原韌體仍是舊機構版本，尚未改為雙輸出回授控制。
請先完成棘輪、定位、鉸鏈與配合試片，再凍結整機尺寸及控制方式。
