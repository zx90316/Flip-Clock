# 模型入口

`assembly.py` 為整機，呼叫各子模型並保留命名組件。`geometry.py` 保存新設計的工廠函式，
`settings.py` 只讀 `config/parameters.yaml`。本目錄沒有原作者檔案匯入。

- `frame.py`、`input_drive.py`：支架、軸承包絡、共同輸入與馬達安裝。
- `clutch_minute.py`、`clutch_hour.py`：兩方向獨立棘輪。
- `transmission_minute.py`、`transmission_hour.py`：40:20:40／60:60 齒輪。
- `drum_minute.py`、`drum_hour24.py`：完整 60／24 片及獨立輸出軸。
- `detent_minute.py`、`detent_hour.py`：定位、手動旋鈕與可調釋放支架。
- `sensors.py`、`guards.py`：採購模組包絡、磁鐵帽及側板。
- `coupon_plate.py`：24／36／48 齒與反向棘輪、配合及鉸鏈試片。
- `clutch_test_rig.py`：單離合器台架。

執行方式見上層 README；一個入口一個 STEP。匯出的分件不回讀成父模型輸入。
