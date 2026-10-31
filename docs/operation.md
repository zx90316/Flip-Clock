# 初次啟用與操作

## 1. 軟體與硬體確認分開

兩板程式已編譯及模擬；機械週期、馬達電壓、方向、電源、RTC 電池、Flash 容量與 BLE 真機相容性尚未驗收。先完成接線文件的盤點，再給馬達供電。新設定只是起測值，不能據此認定機構校準已完成。

ESP 上電保持暫停，RTC 無效或位置未確認都不自動轉動。只刷 ESP 時 Uno 仍被維持 reset，所以 `LINK_WAIT` 正常，BLE 與 UART 維修仍可工作。

## 2. 第一次配對及 Wi-Fi

保持馬達不供電；ESP 由 Uno UART 監控，115200 baud。在刷 ESP 模式中，燒錄完成後先移除 ESP GPIO0→GND、重置 ESP，Uno RESET 仍接 GND 作 UART 轉接。

輸入 `status` 可看 boot_id 與安全狀態。輸入 `pair` 開啟 120 秒窗口，UART 只在此時印出該次六位數 passkey。桌面 BLE 工具或手機 GATT 工具連線後，在系統提示輸入 passkey；訂閱 Event TX 的 indication。未加密、未驗證或未訂閱的寫入不執行命令。

Wi-Fi 僅透過本地 UART 設定，使用一整行：

```text
wifi {"ssid":"你的2.4GHz網路","password":"你的密碼"}
```

這是格式範例，請在維修介面填實際值，不把密碼放進 Git 或一般測試紀錄。回覆只含 `WIFI_SAVED`，不回顯密碼。不開設定 AP。若要改 SNTP 來源：

```text
ntp {"servers":["pool.ntp.org","time.cloudflare.com","time.google.com"]}
```

完成後先斷電，依模式表移除 Uno RESET→GND、D0／D1 信號線與 GPIO0 跳線，恢復正常 I²C，再上電。BLE bond／Wi-Fi 設定保留，boot_id 會改變；重新連線先讀狀態。

若要重新配對，先停機、切 UART 維修模式，輸入 `clear_bonds CONFIRM`，再輸入 `pair`。一般 BLE 命令不能清除 bond 或開啟配對。韌體拒絕 BLE 堆疊預設的自動覆蓋舊 bond 行為。

## 3. 建立時間與機械基準

桌面工具互動模式中的 `time` 會用電腦當下 UTC 寫 RTC、讀回核對，並將 `auto_time=false`；電腦時間本身也須正確。原生手機／GATT 工具使用 `set_time` 的 Unix **秒**，不是毫秒。RTC 維持 UTC，不再加一次 +8 小時。

先確認機構確實為一顆馬達、一頁一分鐘，並核對 720 或 1440 分鐘完整週期。確認後才送例如：

```json
{"op":"set_config","values":{"mechanics_confirmed":true,"cycle_minutes":720,"steps_per_page_u6":136000000,"max_step_rate":200,"acceleration":100,"settle_ms":200}}
```

上面可直接貼入桌面互動工具；它會補 v、id、boot_id 與 LF。720／136 是格式示例及起測值，應改成實際機構設定。GATT 工具則必須自行補完整協定欄位。

先用 `jog 4` 等少量正向步數確認相序、方向與落頁；**jog 後位置會失效**。若震動不轉，停止並查線序，不提高電壓或速率。正式映像不允許反轉；`allow_reverse=true`／負 jog 會拒絕，避免在未驗證機構上反轉。

目視確認當下頁面已完整落下，再輸入 `display 10:30`；這只適用實物真的顯示 10:30 的時候。此操作不轉馬達、不校 RTC，建立顯示索引並將小數餘額設零。

接著 `preview` 查看追趕頁數、預估時間及 plan_id，再輸入 `resume`。超過 60 頁或預估 120 秒須明確使用 `resume large`；它仍逐頁執行、每頁重讀時間。預覽 30 秒後、跨分鐘、改時間／時區／位置／設定後都失效，須重新 preview。

## 4. 校準比例

1. `pause`，等當頁完成與 DISARM；確認實物完整落頁。
2. 必要時少量 jog 對齊，再用 `display` 重建目前頁面基準。
3. 用 `pages N` 正向走已知頁數，記錄送出步數與實際機械基準；跨多頁、整點，最後涵蓋完整機械週期。
4. 用同基準之間總半步數 M／頁數 N 推導 `steps_per_page_u6≈M×1000000/N`。
5. `set_config` 改比例會使位置失效；再目視設定 display，preview／resume。
6. `pause` 後 `save`，只在收到 `persisted:true` 才視為已保存。設定與保存位置可由 status 分別查閱。

比例、基準相位、當前顯示時間是三項不同資料；不要用校 RTC 或顯示偏移掩蓋比例誤差。每頁用定點累積小數，`DONE` 才提交餘額。28BYJ-48 不預設精確 4096 半步，也不沿用參考專案多字元輪的 45 頁模型。

## 5. 日常暫停、停止與恢復

`pause` 完成當頁後停止排程、DISARM；`stop` 優先停止後續相位、關輸出，可能停在半頁，因此保守要求重新確認位置。兩者都不能替代實體馬達斷電開關。

重啟／斷電後，先讀 status，必要時校時；對照實物、jog 對齊、display 確認，再 preview／resume。NVS 的 snapshot 只是保存當時的參考位置；韌體從不把它直接當成重啟現況，也不重播中斷的工作。

通訊失聯／Uno reset／運動逾時進 FAULT，先排除原因，再 `clear`。清除故障仍然位置 unknown。`E_NVS` 先檢查保存及分區狀況；若確實要捨棄設定，可在本地 UART 使用 `reset_config CONFIRM`，RTC 與 bond 保留，重新校準及保存。不要把出廠清除當日常故障排除步驟。

## 6. 自動網路校時

設定 `{"op":"set_config","values":{"auto_time":true}}` 重新開啟 SNTP，再 `save` 才跨斷電保留。實際收到 SNTP 通知、日期合法後才視為網路校時；軟體系統時間或開機計時不構成有效 SNTP 證據。

每次新同步先暫停，讓當頁完成，再解除 armed 寫 RTC、讀回並重建追趕預覽。與有效 RTC 差超過 300 秒時，status 的 `pending_sync_utc` 顯示待確認值；可送：

```json
{"op":"confirm_time","utc_s":實際pending_sync_utc整數}
```

這是額外的確認命令，必須使用實際狀態值，120 秒內有效；韌體會加上等待期間經過秒數。若不打算採用，可用正確手機／電腦時間 `set_time`，它會停用自動校時並丟棄待確認值。任何時間更新都不直接改 display_index；套用後重新 preview／resume。

斷網時以有效 DS3231 走時；RTC 連續三次讀取失敗或三秒沒有有效讀值時，停止自動排程。網路恢復不直接驅動馬達追趕。
