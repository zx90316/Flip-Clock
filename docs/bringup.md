# 從零接線：一次完成一段

正式目錄 **D:\Project\Flip-Clock**。目前已完成 Uno 單板 USB 燒錄與安全待機診斷；下一段是單顆 5V 馬達空載測試。

## 第 1 段：Uno 單板 USB（已完成）

COM3、CH340、ATmega328P；韌體 0.2.0、protocol 1。上傳／校驗成功，STATUS 回覆 BOOT_UNARMED、armed=false、coil_mask=0。記錄在 [hardware/uno-status.json](hardware/uno-status.json)。沒有據此宣稱負載、馬達方向或 RTC 已測。

## 第 2 段：只有 Uno＋ULN2003＋一顆 5V 馬達

使用者已確認馬達銘牌為 **5V**，並選擇先用 Uno USB 的 5V 作短時間試轉。這是獨立空載實驗，與完整裝置外部穩壓供電方案分開；不在本階段接 ESP、RTC 或外部電源。

先拔掉 Uno USB，再接：

| Uno | ULN2003 板 |
|---|---|
| D8 | IN1 |
| D9 | IN2 |
| D10 | IN3 |
| D11 | IN4 |
| 5V | 標示 +／VCC／5V 的馬達供電正端 |
| GND | 標示 −／GND 的電源負端 |

把馬達五線接頭插入 ULN2003 的五針馬達座；不要把馬達線直接接 Uno GPIO。依板上絲印辨識電源端，標示不符時先確認。馬達先脫離機械負載，線及手指避開轉軸。

接好後才插回 USB。未下命令前馬達應不轉動；四個相位指示燈應不持續亮（若有獨立電源燈，常亮可正常）。若插電立即持續轉動、USB 掉線、重開機或明顯發熱，立即拔 USB。

**確認接線後才執行試轉**：VS Code Task `Uno：單顆空載試轉 16 半步（需先接線）`。只跑 16 個正向半步，最高 30 half-steps/s，完成後關閉線圈並 DISARM。位移很小，先觀察驅動板相位燈與軸的輕微動作；不要因看不清就連續大幅加步數。

UART bench 必須明確 BENCH ON；只允許正向 1–256 半步、10–50 half-steps/s、單工作最長 10 秒，使用與雙板相同 CRC／session／seq／去重及 1.5 秒 lease。任何 I2C 主端讀／寫活動都鎖住 bench，須拆除 ESP I2C 並重置 Uno 才能重開，避免兩個來源同時控制。開機及連接序列埠不會自動試轉。

終端機顯示 steps_sent 只代表送完相位；是否平順、方向、USB 供電穩定，要由操作者回報。正式電源仍需測試單顆馬達負載及 ESP Wi-Fi／BLE 尖峰，不能以這次 USB 試轉代替整機供電驗證。

## 第 3 段：ESP 首次燒錄

先停機、斷 USB、拆除剛才 ULN2003 的供電。依 [wiring.md](wiring.md) 的刷 ESP 模式接 Uno RESET→GND、D0／D1 經 BSS138 到 ESP UART、ESP GPIO0→GND，再用**已確認的外部穩壓電源**供 ESP 5V；不要用 Uno 3.3V 腳供 ESP，也不將兩個 5V 電源並聯。

BSS138 UART 路徑須驗證電位／串聯電阻與上拉裕量，不只依絲印猜接。完成後選 ESP 燒錄 Task；成功後移除 ESP GPIO0 跳線並重置 ESP，先透過 UART 開 BLE 配對及設定 Wi-Fi。未完成本段電源確認前不接 ESP。

## 第 4 段：恢復雙主控 I2C

斷電，移除 Uno RESET→GND 及 D0／D1 UART 信號線。GPIO13/14、DS3231 與 BSS138 3.3V 側；Uno A4/A5 在 5V 側。接線及電池要求依 wiring.md。先不給馬達供電，讀 BLE 狀態確認 Uno 0x12／RTC 0x68，再進時間與機構校準。

## 第 5 段：時間、機構與長期驗收

依 operation.md 校 RTC UTC、確認 720／1440 週期及 q、目視 set_display、preview／resume，最後 save。沒有原點感測器，重啟及半頁 stop 後都要重新確認實物。完整週期、掉電、負載與 72 小時走時逐項填 hardware-acceptance.csv；尚未完成不能標成通過。

依據：[Arduino Uno R3 手冊](https://docs.arduino.cc/resources/datasheets/A000066-datasheet.pdf)、[TI ULN2003A](https://www.ti.com/lit/ds/symlink/uln2003a.pdf)。CH340 相容板的保護／穩壓／USB 路徑仍以實物為準。
