# ESP32-CAM＋Arduino Uno 雙主控翻頁時鐘：Codex 工程實作規格

版本：2.0 · 2026-10-31 · 繁體中文

**已納入最新需求：使用者已有 MCP23017；採雙主控；ESP32-CAM 由 Uno R3 刷韌體。**

適用：AI-Thinker classic ESP32 ESP32-CAM、Uno R3、DS3231、28BYJ-48＋ULN2003、8 路 BSS138。MCP23017 保留擴充，基礎版不需要接入。

這是可交給 Codex 執行的工程規格，不是已完成實機驗證的韌體。「必須」為交付條件；「建議」為設計起點；「選配」不代表使用者已持有。接線以馬達確認為 5 V 版本為前提。資料來源已核對，實物與機構須按驗收階段確認。

閱讀順序：方案與零件見 1–3；電源／刷寫／接線見 4–7；RTC 與機構見 8–10；雙板協作與保存見 11–12；BLE／I²C 協定見 13–14；網路與開發／驗收見 15–20。

## 1. 最終方案：ESP32-CAM＋Uno 雙主控

本版依使用者最新決定採用雙主控，且 **ESP32-CAM 韌體由現有 Uno R3 板載 USB UART 燒錄**。正常運轉時 Uno 執行馬達韌體；燒錄 ESP32 時 Uno 的 ATmega328P 保持 reset。這兩種角色不可同時執行。

| 裝置 | 責任 |
|---|---|
| ESP32-CAM | Wi-Fi／SNTP 取得目前時間、BLE 手機校時與微調、DS3231 管理、設定與位置紀錄、計算步數、向 Uno 下命令、核對完成回報 |
| Uno R3 | 接收命令、獨立產生半步時序、加減速、驅動 ULN2003、回報執行步數、通訊中斷時停止 |
| DS3231 | 無網路／主電源中斷時維持時間；電池不供馬達或主控 |
| MCP23017 | 使用者已有，但雙主控的單馬達基礎版不需要；保留未來感測器／按鍵擴充 |

```text
網路時間 SNTP ── Wi-Fi ─┐
手機校時與微調 ── BLE ──┤ ESP32-CAM：時間、設定、計畫與紀錄
                       │ GPIO13 SDA / GPIO14 SCL，3.3 V I²C 主端
                       ├── DS3231，0x68，3.3 V
                       └── BSS138 A2/A3 ↔ B2/B3，3.3 V ↔ 5 V
                                          │
                             Uno A4 SDA / A5 SCL，I²C 從端 0x12
                                          │ D8、D9、D10、D11
                                          ▼
                                     ULN2003 → 28BYJ-48 → 機構

暫時刷 ESP：電腦 USB → Uno 板載 16U2 → D0/D1 → BSS138 A0/A1 → ESP UART0
            此時 Uno RESET→GND，馬達電源關閉；完成後拆除燒錄跳線。
```

方案評估：這樣可讓網路與 BLE 的工作不直接決定每個步進脈衝的時刻，Uno 也有足夠 GPIO。代價是維護兩份韌體，必須處理通訊重送、兩板分別重啟與位置一致性。對目前已有零件而言可行，但它不會自動增加馬達定位精度；已校準的單主控＋MCP23017 原本也可完成一顆馬達的需求。

必須完成：網路校時、RTC 離線走時、BLE 手動校時／校準、NVS 保存設定、保守的斷電恢復、Uno 失聯停機、兩份可重現建置的韌體與測試。相機、microSD、HA、外接藍牙模組不列入基礎版；ESP 的 Wi-Fi OTA 是後續選配。

**時間、軟體記錄的位置、實際機械位置仍是三件事。** Uno 回覆送完 136 步不代表機構真的翻到下一頁。沒有感測器時不能保證卡頁、人工轉動、半頁斷電後的位置；預設重啟要求目視確認，再追趕正確時間。

## 2. 原始 GitLab 程式查核與移植界線

已核對 [GitLab 原始 snippet](https://gitlab.com/-/snippets/4791675) 及其 [raw 原始檔](https://gitlab.com/-/snippets/4791675/raw)。2026-10-31 下載 raw 檔的 SHA-256：

```text
A5D289BE74E69BF677B9564397B8C962F3F34E7969EC4E59E8C4A9FE95A9D8AF
```

原檔的關鍵事實：

| 原始項目 | 已核對內容 |
|---|---|
| 平台 | ESPHome YAML；`esp32dev`；Arduino framework |
| 取得時間 | SNTP，每分鐘觸發；含 Wi-Fi、HA API、OTA 設定 |
| 馬達 | 單組 ULN2003；GPIO16、17、5、18；HALF_STEP |
| 參數 | 每分鐘 136 步；手動小時 8190 步；最高 900 steps/s；加速度 400 steps/s² |
| 完成處理 | `sleep_when_done: True`；保存 `last_reported_time` |

本文移植判斷：原檔在送出目標後即更新時間，不能據此證明機械完成；校時倒退時加一天的處理也不適合直接沿用。另有 `136 × 60 = 8160` 與手動小時 `8190` 不一致，不能把兩者當成同一組已校準比例。新實作應由同一個每頁步數推導整點移動。

頁面討論區另有 2025-03-24 留言版本，加入誤差累積與顯示校正；它與 raw 原檔不同。不得將留言版當成原檔，也不得假定留言中的每圈頁數等於使用者機構。新韌體採獨立 Arduino C++ 實作，保留功能概念，重新建立運動與儲存模型。原頁未確認有適用的程式授權；若日後要散布直接複製的程式碼，先確認授權，勿把公開可讀等同任意授權。

## 3. 已有硬體、待確認與選配

| 項目 | 狀態／用途 |
|---|---|
| AI-Thinker classic ESP32 ESP32-CAM | 指定通訊主控，不套用 S2／S3／C3 板型 |
| Arduino Uno R3 | 已有，正常運轉是馬達控制器；維修時也是 ESP 燒錄轉接器 |
| DS3231 | 已有；RTC 模組版本、電池與充電路徑待確認 |
| 28BYJ-48＋ULN2003 | 已有；馬達究竟 5 V 或 12 V 必須讀銘牌，本文電源圖以 5 V 為前提 |
| 8 路 BSS138 模組 | 已有；已查看照片上的 VCCA／VCCB、A0–A7／B0–B7 |
| MCP23017 | 已有；基礎雙主控版本不接入，可留待擴充 |
| 電源、USB 線、端子、杜邦線、電池 | 未確認持有；施工前盤點 |
| 上拉／下拉電阻、去耦及儲能電容 | 依實物是否已有決定是否補足，不假設都已擁有 |
| 原點／位置感測器 | 選配；若要無人工位置恢復才追加 |
| FRAM、備援電源、獨立馬達電源關斷 | 選配，不列入目前能力 |
| MCP23008、另一塊 ESP32、USB UART 轉接器 | 不需要為本方案預先購買 |

首次轉動前確認：馬達電壓、線圈／插座線序、每頁對應幾分鐘、機械週期 720 或 1440 分鐘、正向方向、可否反轉、電源規格、RTC 電池安全。若尚未確認，Codex 仍可完成模擬與編譯，但自動轉動功能預設鎖住。

## 4. 電源、電平轉換與兩種供電情境

### 4.1 正常運轉供電

一顆 **5 V** 28BYJ-48 的系統，可從可靠的穩壓 **5 V／2 A** 作初步電源選型；這是設計建議，不是已測得需求，也不代表使用者已持有。依線圈、BLE／Wi-Fi 尖峰電流及線損驗證。

- 外部 5 V 分支供 ESP32-CAM 的明確 **5V** 腳、ULN2003 馬達正端，以及 Uno 適當的 5 V 供電入口。不能把 5 V 接 ESP32 3V3／GPIO。
- Uno 可以透過由穩壓電源供電的 USB 入口，或經確認的 5V 腳供電。從 5V 腳注入會繞過部分輸入保護，只能使用已驗證穩壓電源；不能把 5 V 接 VIN／圓孔插座期待正常 5 V 穩壓輸出。
- 正常使用外部電源時，不同時把 Uno 的外部 5 V 與電腦 USB 的 5 V 並接。需連電腦刷寫／監控時，先斷開 Uno 的外部正電源路徑，再以 USB 供 Uno；ESP／馬達可另用外部電源，僅共地。具隔離功能的電源切換器或去除 VBUS 的線是選配，不能假設已有。
- 馬達電源直接由供電分支供給，不經 Uno 的板載穩壓器、5V 排針走線或 ESP32 板。馬達回流直接回電源，控制板共地。
- DS3231 主電源接 ESP32 3V3；BSS138 低壓側參考接 ESP32 3V3，高壓側參考接 Uno 5V。
- 不使用 Uno 的 3.3V 腳供 ESP32-CAM。不要把不同 5 V 電源輸出直接並聯。
- 裸 IC 就近配置 100 nF；板端儲能電容可從 220–470 µF、耐壓 ≥10 V 起測。這些元件未確認已有；依模組已有電容與量測結果決定，不盲目堆加。
- 保留 ESP32 brownout 偵測；檢查馬達動作＋Wi-Fi／BLE 同時工作時的板端電壓及溫升。

### 4.2 BSS138 照片與用途

照片可辨識電源及通道絲印，無法由照片單獨證實所有料號、阻值與電路方向。依使用者描述按 BSS138 設計；接線前核對低／高壓側。下表以 **A 側低壓、B 側高壓** 為條件，若實物相反，整組對調。

| 腳位 | 連接 |
|---|---|
| VCCA | ESP32-CAM 3V3 |
| VCCB | Uno 5V |
| 兩側 GND | 與 ESP32、Uno、RTC、ULN、電源共地 |
| A2 ↔ B2 | 正常 I²C SDA：ESP GPIO13 ↔ Uno A4 |
| A3 ↔ B3 | 正常 I²C SCL：ESP GPIO14 ↔ Uno A5 |
| A0 ↔ B0、A1 ↔ B1 | 只在刷 ESP 時用，詳第 5 節；正常時拆下信號線 |
| 其他通道 | 不接；上下重複電源腳先量測是否同網 |

這不是電源穩壓器，也不能驅動馬達。I²C 開漏線是此類 MOSFET 電平轉換的適用情境；UART 有上拉與速度限制，須另外驗證。兩側各自上拉至各自電源，低壓側絕不可出現 5 V。未通電的板不要由信號線反向供電；斷電接線，不帶電插拔。[Nexperia AN10441](https://assets.nexperia.com/documents/application-note/AN10441.pdf)

## 5. Uno R3 暫時作 USB UART 燒錄器

### 5.1 為何 D0 對 RX、D1 對 TX

標準 Uno R3 的 ATmega16U2 負責 USB UART。把 **Uno 的 ATmega328P RESET 接 Uno GND**，使主控保持重置、UART 腳位不主動驅動；保留板載 USB UART 正常工作。不需燒入 ArduinoISP，不需 SoftwareSerial，也不需重新燒錄 16U2。

Uno 排針 D0/RX 是以 ATmega328P 命名；從 USB UART 看，它接到 **16U2 的 TX**。D1/TX 則接到 **16U2 的 RX**。因此使用這種旁路接法時，是 D0→ESP32 RX、ESP32 TX→D1；若改用真正 USB UART 轉接器，則依轉接器 TX→ESP RX、RX←ESP TX。

以上依 [Arduino Uno R3 官方原理圖](https://docs.arduino.cc/resources/schematics/A000066-schematics.pdf) 判讀。相容板若採 CH340 等晶片，須確認其電路與輸入門檻，不直接套用 16U2 的電氣結論。

### 5.2 燒錄接線表

以下採兩路電平轉換，先將馬達供電斷開並移除 microSD 卡。Uno 若原本接外部 5 V，先斷開該正電源路徑，再用電腦 USB 供 Uno，避免兩個 5 V 輸出並接：

| 起點 | 經過 | 終點／用途 |
|---|---|---|
| Uno RESET | 跳線 | Uno GND；必須持續接著，不是按一下放開 |
| Uno D0/RX | B0 → A0，5 V 降到 3.3 V | ESP32-CAM U0R／GPIO3 |
| ESP32-CAM U0T／GPIO1 | A1 → B1，3.3 V 升到 5 V | Uno D1/TX |
| Uno 5V | 只作高壓側參考 | 轉換器 VCCB |
| ESP32-CAM 3V3 | 只作低壓側參考 | 轉換器 VCCA |
| 外部穩壓 5 V | 獨立供電線 | ESP32-CAM 5V |
| 外部電源負端、Uno GND | 共地線 | ESP32-CAM GND、轉換器 GND |
| ESP32-CAM GPIO0 | 燒錄時接地 | 復位時進入 UART 下載模式 |

**不要把 Uno 5V 與外部電源 5 V 並接。不要把 Uno RESET 與 ESP32 RESET 綁在一起。** 這裡 Uno 主控長期維持 reset，ESP32 則需獨立按板上的 RST／重新上電。

### 5.3 3.3 V 邏輯相容性與實際裕量

1. Uno→ESP32 的方向必須降壓；ESP32 GPIO 不耐 5 V。Uno 板上的串聯電阻不構成可靠的 5 V→3.3 V 轉換。
2. 回程 ESP32→Uno：官方 ATmega16U2 標準 I/O 的 VIH 最低為 **2.0 V**，因此 3.3 V 回程在原廠 Uno R3、328P 持續 reset、無額外 5 V 上拉的前提下，可直接接 D1。不能誤用 ATmega328P 或其他晶片門檻判定這條回程。本表仍提供兩路轉換方式，方便現有模組使用；它不是唯一可行接法。[ATmega16U2 datasheet，DC Characteristics](https://ww1.microchip.com/downloads/en/DeviceDoc/doc7799.pdf)
3. 官方 Uno R3 的兩條 UART 路徑各含 **1 kΩ 串聯電阻**。與 BSS138 兩側上拉共同作用時，低電位可能被抬高。以兩側各 10 kΩ 上拉及理想低輸出粗估，Uno 送低時轉換線約可到 0.69 V；實際還有輸出低壓與元件誤差，不能只看到「3.3／5 V」標示就保證穩定。
4. 接上 ESP32 前先驗證方向與靜態電壓；正式測試觀察低／高電位及邊緣，ESP32 在 3.3 V 下的 VIL 上限約為 0.25×VDD＝0.825 V，應留足裕量。沒有示波器時，至少完成多次完整上傳及驗證，但這不能取代電氣裕量量測。
5. 先用 115200 baud、短線；不穩時可試 57600／38400，仍須先排除電源、共地、串聯電阻與上拉問題。降速只能改善時序，不能解決低電位過高。若不符合門檻，停止用此組合；可改用經設計驗證的單向 UART 電平轉換或選配 3.3 V USB UART。
6. 不直接沿用前次對話的外接「1 kΩ＋2 kΩ」分壓數值：Uno 已有的串聯 1 kΩ 必須一起算入，否則輸出電壓不同於裸 5 V TX 的計算。

燒錄時兩側參考電源都要存在，避免一側關機仍由 UART／上拉反向供電。裝拆前先移除信號連線或讓兩側斷電，勿帶電改接。

### 5.4 手動下載步驟

1. 關閉序列監控視窗。確認 Uno USB 正常顯示 COM 埠，328P RESET 已接 GND。
2. 選擇 **AI Thinker ESP32-CAM** 開發板，而不是因 COM 埠來自 Uno 就選 Arduino Uno。
3. 外部 5 V 供 ESP32-CAM；GPIO0 接 GND，再按 ESP32-CAM RST。GPIO2 不可被外接模組拉高而阻止下載。
4. 以上述 COM 埠上傳。若停在 Connecting，確認接線後再按 ESP32-CAM RST；不依賴 Uno 的 DTR 自動重置 ESP32。
5. 成功後移除 **ESP32 GPIO0→GND**，再按 ESP32 RST 正常開機。保留 Uno RESET→GND，直到不再作 USB UART。
6. 打開 115200 序列監控，確認韌體版本、重置原因、板型及安全待機狀態。初版不得一上電就轉馬達。

若仍看到下載模式，檢查 GPIO0 跳線；若能看到 log 但無法上傳，優先查 PC→ESP 路徑與進入下載模式；若上傳中途失敗，查電源與電平裕量。[Espressif 官方 Boot Mode Selection](https://docs.espressif.com/projects/esptool/en/latest/esp32/advanced-topics/boot-mode-selection.html)

## 6. 正常運轉接線與腳位限制

### 6.1 ESP32、Uno 與 RTC 的 I²C 接線

| 訊號 | 3.3 V 側 | BSS138 | 5 V 側 |
|---|---|---|---|
| SDA | ESP GPIO13＋DS3231 SDA | A2 ↔ B2 | Uno A4／SDA |
| SCL | ESP GPIO14＋DS3231 SCL | A3 ↔ B3 | Uno A5／SCL |
| 邏輯電源 | ESP 3V3＋RTC VCC | VCCA／VCCB | Uno 5V |
| 地 | ESP GND＋RTC GND | GND | Uno GND＋ULN GND |

DS3231 的 SQW／32K／RST 第一版不接。Uno R3 上另外標示的 SDA／SCL 與 A4／A5 是同一組訊號，不是第二個 I²C 控制器。

ESP 唯一主端：`Wire.begin(13, 14, 100000)`。Uno 從端：`Wire.begin(0x12)`。RTC 位址是 0x68；兩者不衝突。第一版固定 100 kHz，不需要每半步都傳 I²C，只傳整段步數並輪詢進度。不要讓 Uno 也在同一組 Wire 當 RTC 主端形成未設計的多主端系統。

兩側都要有適當上拉。BSS138 及 RTC 模組可能已有上拉，需量測並聯等效值；可由約 4.7 kΩ 等級的等效設計起評估，不能每塊板重複加電阻。先用短線約 10–20 cm。Uno AVR Wire 會啟用內部上拉，故更不能把 5 V Uno I²C 與 ESP 直接短接。ATmega328P 的 TWI 高電位規格也不能只套用一般 GPIO 的門檻。[Arduino AVR Wire 原始碼](https://raw.githubusercontent.com/arduino/ArduinoCore-avr/master/libraries/Wire/src/utility/twi.c)、[ATmega328P TWI 電氣規格](https://ww1.microchip.com/downloads/en/DeviceDoc/Atmel-7810-Automotive-Microcontrollers-ATmega328P_Datasheet.pdf)

### 6.2 Uno 驅動 ULN2003

| Uno | ULN2003 |
|---|---|
| D8 | IN1 |
| D9 | IN2 |
| D10 | IN3 |
| D11 | IN4 |
| GND | GND／負端 |
| 無 | 馬達正電源由外部穩壓 5 V 直接供給 |

Uno 輸出 5 V 邏輯，這四條線不經 BSS138。馬達五線插座只接驅動板；若使用裸 ULN2003，COM 接馬達正端以連通反電動勢箝位二極體，GND 接共地。模組通常已處理，但仍需檢查。線色不是充分接線依據。[TI ULN2003A datasheet](https://www.ti.com/lit/ds/symlink/uln2003a.pdf)

建議確認 IN1–IN4 是否已有可靠下拉；沒有時各加約 10 kΩ 下拉到 GND（需盤點／補料），以降低 Uno reset／bootloader 期間意外通電。Uno 開機第一件事是先將四個輸出 latch 設低再設 OUTPUT。D8–11 同在 AVR PORTB 低四位元，可用遮罩一次更新，保留高四位。若採此實作，明確限制 Uno R3／ATmega328P，勿套用其他 Arduino 板。

### 6.3 ESP32-CAM 的限制

| GPIO | 限制／本方案處理 |
|---|---|
| 13／14 | I²C；與 SD 共用，所以不插 microSD、不啟用 SD_MMC |
| 1／3 | UART0 燒錄與維修；正常不接 Uno D0／D1 |
| 0 | 啟動 strapping／相機 XCLK；只有刷 ESP 時接 GND |
| 2 | 下載啟動相關；不外接拉高負載 |
| 4 | 板載白色閃光 LED，不作馬達腳 |
| 12 | 開機拉高可選 1.8 V VDD_SDIO，導致 3.3 V Flash 啟動失敗；不用 |
| 15 | strapping／開機訊息相關；不用 |
| 16／17 | PSRAM CS／CLK，不為本專案回收 |
| 5／18 | 相機相關，不照搬原 snippet 的腳位 |
| 6–11 | Flash 相關，不用 |
| 34–39 | 晶片端僅輸入且部分接相機，不用作輸出 |

相機不初始化，無需為了馬達關閉 PSRAM。若拔相機排線，必須斷電。Ai-Thinker 舊原理圖網址目前導向文件首頁，本次核對使用 Seeed 保存的 ESP32_CAM V1.6 原圖副本及 Espressif 定義；相容板仍以實物為準。[原理圖副本](https://github.com/SeeedDocument/forum_doc/blob/master/reg/ESP32_CAM_V1.6.pdf)、[Espressif 相機腳位](https://raw.githubusercontent.com/espressif/arduino-esp32/master/libraries/ESP32/examples/Camera/CameraWebServer/camera_pins.h)、[ESP32 datasheet](https://documentation.espressif.com/esp32_datasheet_en.html)

## 7. MCP23017／MCP23008 的定位

目前單顆馬達由 Uno D8–11 直接控制，所以 **MCP23017 不需接入，MCP23008 不需購買**。不用為了已有零件而增加通訊故障點。

| 方案 | 適用性 |
|---|---|
| 本版：ESP32＋Uno | 利用現有兩塊主控；Uno 控制馬達，ESP 管理時間與通訊；需兩份韌體與可靠命令協定 |
| 替代：ESP32＋現有 MCP23017 | 只維護一份主控韌體；以 I²C 輸出四相，需實測時序與匯流排失效時的線圈狀態 |
| 替代：ESP32＋MCP23008 | 8 個位元足夠單馬達，原推薦理由是避開 ESP32-CAM 的啟動腳；但使用者已有 23017，無需重買 |

日後擴充按鍵／原點感測，可將 MCP23017 放在 ESP 的 3.3 V I²C 支路，VDD=3.3 V，A0–A2 固定接地取 0x20，/RESET 保持可靠高電位，100 nF 去耦，SDA/SCL 接 GPIO13/14。這需要辨識裸 IC 或模組的穩壓、上拉與 reset 配置；不能直接假設任一模組 VIN 都接受 3.3 V。

新版 MCP23017 資料表指定 **GPA7、GPB7 只能輸出**，不能安排成感測器輸入。若在 5 V 供電，其 I²C 高電位門檻為 0.8×VDD，不能假定 3.3 V 直接合格。23008 與 23017 的暫存器位址不同，不能只換晶片名稱。這些擴充不列入目前必做功能。[MCP23017 官方 datasheet](https://ww1.microchip.com/downloads/aemDocuments/documents/APID/ProductDocuments/DataSheets/MCP23017-MCP23S17-16-Bit-IO-Expander-with-Serial-Interface-DS20001952.pdf)、[MCP23008 官方資料](https://www.microchip.com/en-us/product/MCP23008)

## 8. DS3231 電池、校時與有效性

**DS3231 晶片本身沒有電池充電器；充電風險來自部分 breakout 板額外的線路。** 模組品牌與版本尚未提供，不得直接判定使用者持有 ZS-042，也不得依照片中的電平轉換板推測 RTC 板。

使用 RTC 前必須：

1. 拿下電池、斷開電源，辨識 VCC→電池正極是否有二極體與電阻充電路徑。部分 ZS-042 常見約 200 Ω＋二極體，但標號與阻值可能不同。
2. **不可讓不可充電 CR2032 連在會充電的路徑上。** 不把「改供 3.3 V」當成永久安全保證，因電池放低、板型差異及將來誤接 5 V 仍有風險。
3. 若有充電路徑，應先確認電路，再由使用者停電拆電池後移除該充電支路元件，保留電池→VBAT 路徑；不能要求盲目拆某個 R／D 標號。無法確認時先不用電池，只做通電測試，斷電保持測試標記未完成。
4. 不把改裝 LIR2032 當成自動安全解方。簡單電阻＋二極體不等於合格鋰電充電管理。優先採明確無充電路徑、搭配適當 CR2032 的配置。
5. 主方案以 3.3 V 供模組，確保上拉也是 3.3 V。若確實需要 5 V 模組電源，不能只移掉 5 V 上拉後直接改上拉 3.3 V 就宣稱符合規格：DS3231 的 VIH 規格與 VCC 有關，應完整做 I²C 電平轉換。

上述模組差異可參考作者對實板的[第一手 ZS-042 充電線路分析](https://www.onetransistor.eu/2019/07/zs042-ds3231-battery-charging-circuit.html)；晶片電源、OSF 及備援行為以 [Analog Devices DS3231 datasheet](https://www.analog.com/media/en/technical-documentation/data-sheets/ds3231.pdf) 為準。

韌體要求：

- RTC 內存放 **UTC**，使用 24 小時制；本地顯示另加時區偏移。預設 UTC+08:00，第一版不實作夏令時間自動規則。
- 啟動讀取 OSF（Oscillator Stop Flag）、日曆合法性、I²C 結果。OSF=1、日期不合法或讀取失敗，均 `time_valid=false`，禁止自動走時。
- 不得每次開機用編譯日期覆寫 RTC。只在有效的使用者校時命令後寫時間、讀回核對，再清除 OSF／標記有效；確認使用函式庫的 `adjust()`／`lostPower()` 實際行為。
- DS3231 沒有供應用程式任意儲存位置的通用備援 SRAM；旁邊的 AT24C32 若存在是另一顆 EEPROM，不當成 FRAM。
- 電池只維持 RTC 計時，不供 ESP32、BLE、馬達。RTC 失聯時可暫時計算 RAM 時間供診斷，但超過連續 3 次讀取失敗或 3 秒未有有效讀取時停止自動排程，待確認恢復。

## 9. 機械模型、半步輸出與校準

### 9.1 第一版的機構範圍

第一版只控制 **一顆馬達**，預期每一個機械翻頁增量對應顯示增加一分鐘。若實際是獨立時／分馬達、多個數字輪或一頁不是一分鐘，應先修訂機械模型，不能只複製本文件步數。

`cycle_minutes` 僅允許 720 或 1440，分別代表機構的 12／24 小時完整重複週期。它不只是手機顯示格式，改參數不能把 12 小時機構變成 24 小時機構。首次設定前維持未確認狀態；可提供 720 作介面預選，但必須由操作者確認後才能自動運轉。

原檔的 136 步僅作初始測試值。不可宣稱所有 28BYJ-48 都精確 4096 半步／輸出軸一圈，也不能預設每圈 30 頁或固定採用 135.86。齒輪版本、傳動比與機構均須實測。

### 9.2 Uno 執行半步相位

明確定義 bit0=IN1、bit1=IN2、bit2=IN3、bit3=IN4：

```text
phase index:  0    1    2    3    4    5    6    7
output mask: 01   03   02   06   04   0C   08   09   （十六進位）
```

先用低速空載確認相序與實際方向；若只震動，先查線序，不直接加速。半步索引須跨移動保留，不能每次翻頁都從 phase 0 重啟。到位後預設關閉全部線圈，避免持續發熱；再次啟動時恢復相位策略必須實測是否造成偏移。未做位置感測的 `completed` 只代表成功送完預定相位，不是證實翻頁成功。

起始設計值：最高 200 half-steps/s、加速度 100 half-steps/s²、每次整頁完成後約 100–300 ms 的可調機械穩定時間。參數都需實機驗證，不能以原檔 900 steps/s 視為最低要求。未驗證前保持單相／雙相最多各一或二線圈通電，不使用全四線圈常通。

正常自動走時只允許機構已確認的正方向。`allow_reverse=false` 為預設。反轉容易卡頁或受齒隙影響，只有操作者已確認機構允許且啟用設定後，才提供反向微調。

### 9.3 小數步數補償

使用整數定點或有理數，禁止每頁直接四捨五入後永久丟掉小數。建議：

```text
D = 1,000,000
q = steps_per_page_u6       // 每頁半步數 × D，例如 136,000,000
r = fractional_remainder  // 0 <= r < D

計畫前進 N 頁：
total = r + N * q          // uint64_t，並做溢位與 N 範圍檢查
steps = total / D
next_r = total % D
```

`next_r` 與顯示索引只在 ESP 收到並核對 Uno 對應工作成功結束後更新；中途停止、timeout 或掉電不能套用整段目標。為了可中止與追趕，正式執行以「一頁」為最小完成單位，連續多頁只是依序排程多個一頁 job。微調 raw steps 不自動增加顯示分鐘，也不擅自改每頁比例。

若 q=`136533333`、r=0、N=30，整數算式應產生 4095 步及餘數 999990；這是定點截斷規則的測試例，不是宣稱真實機構應走 4095 步。另測試分 30 次一頁與一次算 30 頁結果完全相同。

### 9.4 機械校準程序

1. 暫停自動走時，操作者目視並以少量 `jog_steps` 對齊到一個可靠的翻頁基準。
2. 設定實際正在顯示的時／分。此操作建立邏輯位置，**不改 RTC，也不轉馬達**。
3. 以已知的整頁數移動，累計實際送出半步數；至少跨多頁、數十分鐘與整點進位，最好覆蓋完整機械週期。
4. 量測相同機械基準間所需總步數 M，對應 N 頁，校準 q≈M/N。不能只用「最後數字差幾分鐘」推定所有相位偏移。
5. 分別處理比例（每頁步數）、基準相位（微調）及顯示位置（目前頁面），三者不可混為一個時間偏移。
6. 保存通過測試的參數後，再跑完整週期；記錄漏頁、重頁、半頁、整點進位失敗與齒隙。

## 10. 時間模型、排程與追趕

### 10.1 明確分開的資料

| 資料 | 意義 | 可信來源 |
|---|---|---|
| `rtc_utc_s` | 現在 UTC 秒數 | 有效 DS3231 讀值 |
| `utc_offset_min` | 本地時區偏移，預設 +480 | 已保存設定 |
| `display_index` | 本次 session 由 Uno 回報完成送步對應的顯示分鐘，0…P−1 | 操作者確認後，由完成事件遞增 |
| `position_confidence` | unknown／user_confirmed／open_loop／homed | 不同來源不得混淆 |
| `pending_target` | 計畫到達的位置 | 不得當成已完成的位置 |
| `last_confirmed_snapshot` | 最近明確保存的參考狀態 | 歷史資訊，不保證等於斷電當下實物 |

第一版支援日期範圍 2000-01-01 至 2099-12-31。內部計算 epoch、差值與乘法使用明確的 64-bit 型別；不得依賴平台 `int`／`time_t` 寬度，也不得把手機傳來的毫秒誤當秒。

### 10.2 正常追趕公式

設 P=`cycle_minutes`，使用正餘數函式 `mod_pos(x,P)`：

```text
local_minute = floor((rtc_utc_s + utc_offset_min * 60) / 60)
target_index = mod_pos(local_minute, P)
forward_pages = mod_pos(target_index - display_index, P)
```

必須同時滿足 `time_valid`、機構設定已確認、位置可用且自動模式已啟用，才可執行。模數只表示面盤循環，不表示 UTC 曾倒退就能任意補一整天。

- RTC 約每 250 ms 讀一次，使用分鐘索引判定變化，避免每分鐘重複排程。開始翻頁的設計目標為分鐘邊界後 1 秒內；實際落頁還需要馬達時間，不宣稱瞬間換頁。
- 不以 `delay(60000)` 走時，也不以 MCU 開機時間當永久時鐘。
- 時間設定、時區變更、偵測到 RTC 倒退／異常跳動後，進入暫停與追趕預覽；不得直接做 P−1 頁的大幅前進。
- 預設 `max_auto_catchup_pages=60`、單次允許追趕的預估時間上限 120 秒。超過任一項進入 `NEEDS_CATCHUP_CONFIRM`，由使用者確認預覽或手動調整實物後重新設定顯示。
- 預覽包含目標、本次頁數、估計時間、設定版本及 `plan_id`。確認時若位置、時間／時區或設定已改變，舊預覽作廢。
- 長追趕逐頁執行，每頁完成後重新讀取時間與目標；若手機校時要求改變目標，先拒絕 busy 或安全暫停後再受理，不讓兩個命令同時改位置。
- 取消不回滾已走完頁數；在半頁停止則標記位置未知。停止後不得以原目標標記成功。
- 大幅校時倒退：預設停下等待使用者選擇「等真實時間追上」或「確認向前繞一圈」；第一版最低需求是暫停＋明確向前追趕確認，不強制實作自動等待策略。

## 11. 雙主控架構與運動交易

### 11.1 分工與唯一權威

| ESP32 模組 | 工作 |
|---|---|
| NetworkTime／RtcService | 網路及 RTC 時間、有效性、UTC／時區 |
| ClockPlanner／CalibrationService | 機構週期、每頁步數、小數餘額、追趕與校準 |
| UnoLink | 唯一 I²C 主端工作佇列、session、序號、重送、心跳、進度核對 |
| SettingsStore | NVS 設定、快照、schema／CRC／版本 |
| BleProtocol／Supervisor | 手機協定、配對與狀態機；callback 不直接執行運動 |

| Uno 模組 | 工作 |
|---|---|
| LinkEndpoint | 收固定長度命令、驗證 CRC／序號／session、提供狀態快照 |
| MotorEngine | 非阻塞半步、加減速、phase、實際送出的步數 |
| SafetySupervisor | 心跳期限、運動期限、stop、watchdog、開機關線圈 |

RTC 與 NVS 的主要權威都在 ESP32。Uno 不自行算日期、不用 EEPROM 每分鐘保存位置；它只依有效 session 執行有上限的步數。ESP 管理邏輯顯示索引與小數 r；Uno 管理本次開機的相位與執行數，不能兩端各自補償同一個小數。

### 11.2 一頁一次交易

```text
ESP 計畫一頁：steps、next_r、target_index
  → 送 MOVE_STEPS(session, job_seq, steps, rate, acceleration, timeout)
Uno 驗證、回 accepted，開始送相位
  → ESP 每 50 ms 左右讀進度，另定期送 heartbeat
Uno 送完步數並將四相輸出設低，回 DONE(job_seq, executed_steps)，保持結果供重讀
  → ESP 核對 session、job_seq、完整步數與無錯誤
  → 才更新 display_index／r；等待 settle_ms；再計畫下一頁
```

收到 I²C ACK 只代表從端收到了 bytes，不等於命令有效；收到 accepted 不等於馬達完成；DONE 不等於機械實際到位。三個層級都須在 log／BLE 分開。

ESP 不發送每個半步命令。一次只允許一個運動 job；長追趕拆成整頁 job。ACK／DONE 遺失時重送**同一個序號與相同內容**，Uno 回同一狀態，不重跑。ESP 只對尚未提交的完成序號更新一次邏輯位置。

### 11.3 重置、心跳與停止

- Uno 上電四線圈關閉，狀態 `BOOT_UNARMED`；不因收到過去的 MOVE 就啟動。先 OPEN_SESSION，送匹配 session 的 HEARTBEAT，再 ARM；ARM 要求最近有效 heartbeat 不超過 500 ms。
- ESP 每 250 ms 發有效 heartbeat；Uno 超過 1500 ms 沒收到匹配 session 的有效 heartbeat，停止後續相位並關線圈，撤銷 armed，回 `LINK_TIMEOUT`。若在半頁，位置未知。
- Uno 使用硬體 watchdog 作最後保護，例如 2 秒起測；主迴圈處理正常才餵狗，ISR 不餵狗。驗證所用 Uno bootloader 與 watchdog reset 行為，避免重啟迴圈。
- 兩端都可 `pause`，語義是當前頁完成後停止排程；`stop` 是盡快停止相位，可能停半頁。正常通訊時 stop 目標反應 ≤100 ms；失聯靠 lease，驗收關閉線圈 ≤1.6 秒。
- Uno 自己重啟：回 session=0、unarmed，ESP 立即使位置 unknown，不把中斷工作重新當新命令執行。
- ESP 自己重啟：先不續發工作，待 Uno 停止／解除 armed，再建立新 session；位置 unknown。NVS 的舊目標不可當作已完成。
- 若 `clear_fault` 成功，只恢復通訊／安全狀態，不自動恢復位置可信度。停止後仍需目視確認。
- Uno 經 USB 開啟序列埠可能被 DTR 重置，屬預期重置事件；現場維修先 pause／停馬達。

### 11.4 排程與共享資料

ESP 的 BLE、Wi-Fi 事件 callback 只入有上限佇列，不能在 callback 中同步等待 Uno 完成。I²C 有 timeout；出錯後受控重試，不無限阻塞。網路連線不得阻塞心跳。

Uno 的 `Wire.onReceive`／`onRequest` 由中斷路徑呼叫：receive 只複製最多 32 bytes 至固定 buffer 並置旗標；request 只回已準備好的固定快照。CRC、命令判斷、Serial log、加減速、EEPROM 操作都在主迴圈。禁止 `delay()`、動態配置或在 callback 裡走馬達。

AVR 上 16／32-bit 欄位不一定原子，使用短暫 atomic block 或雙 buffer 交換，避免讀到撕裂的步數；`volatile` 本身不是互斥。不得因 I²C 長時間關中斷破壞步進。主迴圈依 monotonic `micros()` 排程，使用可跨 rollover 的差值比較；逾期不瞬間補發多步。[Arduino AVR Wire.h](https://raw.githubusercontent.com/arduino/ArduinoCore-avr/master/libraries/Wire/src/Wire.h)、[Wire callback 實作](https://raw.githubusercontent.com/arduino/ArduinoCore-avr/master/libraries/Wire/src/Wire.cpp)

### 11.5 ESP 狀態機

```text
BOOT_SAFE → LINK_WAIT → NEEDS_TIME／NEEDS_CALIBRATION → PAUSED
PAUSED → 有效追趕預覽與 resume → IDLE → WAIT_ACCEPT → MOVING → SETTLING → IDLE
IDLE／PAUSED → 超過自動追趕限額 → NEEDS_CATCHUP_CONFIRM
任何狀態 → 通訊、儲存或時程錯誤 → FAULT
MOVING → pause：等當頁完成後 PAUSED
MOVING → stop：停止相位；若半頁則 NEEDS_CALIBRATION
```

LINK_WAIT 期間不得送運動，但 BLE 與本地序列維修仍須可用，不能因 Uno 尚未上線或正在充當燒錄器而阻塞配對／設定。NEEDS_TIME 與 NEEDS_CALIBRATION 可以同時存在於 readiness flags，狀態欄只顯示目前優先處理項目。FAULT 不自動續跑；清除故障後重查時間、機構與位置可信度。所有狀態轉移由單一 Supervisor 決定，BLE／網路 callback 只提出事件。

## 12. 持久化、斷電恢復與壽命

### 12.1 要保存的設定

使用 ESP32 NVS，可透過 Arduino `Preferences` 實作。保存的是可跨斷電保留的設定；不等於無限寫入壽命，也不等於任何故障都不會損毀。[Preferences 官方說明](https://docs.espressif.com/projects/arduino-esp32/en/latest/tutorials/preferences.html)、[NVS 官方說明](https://docs.espressif.com/projects/esp-idf/en/stable/esp32/api-reference/storage/nvs_flash.html)

建議一個經明確序列化的設定 blob，欄位如下：

| 欄位 | 說明／初始值 |
|---|---|
| `magic`、`schema_version`、`generation`、`crc32` | 格式與完整性；CRC 範圍、byte order 必須固定 |
| `board_profile` | `AI_THINKER_ESP32_CAM_DUAL_UNO`；不能由 BLE 任意改接腳 |
| `mechanics_confirmed` | false，完成機構盤點才設 true |
| `cycle_minutes` | 720 或 1440；未確認不能自動啟動 |
| `steps_per_page_u6` | 起測 136000000，需校準 |
| `forward_direction`、`allow_reverse` | 實測方向，反轉預設 false |
| `max_step_rate`、`acceleration`、`settle_ms` | 初始 200、100、200；單位明列 |
| `utc_offset_min` | +480；允許 −720…+840 |
| `max_auto_catchup_pages`、`max_catchup_seconds` | 60、120 |
| `release_coils` | v1 固定 true，Uno 在 DONE／STOP 關閉輸出；不允許 BLE 改成持續通電 |
| `recovery_policy` | `SAFE_RECONFIRM` |
| `auto_time` | true；手動校時後關閉自動網路覆寫，可明確再開啟 |
| `last_confirmed_snapshot` | UTC、顯示索引、r、Uno phase、設定版本與來源；只供參考 |
| `checkpoint_interval_min` | 預設 30；僅停止／落頁後保存最近完成位置，0 可關閉定期快照 |

BLE bond 金鑰使用 BLE stack 的正式儲存機制，不混入可匯出的普通設定。不得把密碼、金鑰、Wi-Fi 憑證輸出到一般 log 或 BLE 狀態。

### 12.2 寫入規則與一致性

- 編輯值先放 RAM；`save_config` 才提交，連續未變更的保存不重寫。短時間大量寫入要節流並回覆原因。
- 至少採 A／B 兩份有 generation 與 CRC 的 blob：寫入較舊 slot、確認成功並讀回後才回覆已保存；開機選最新完整有效版本。不得用多個獨立 `putX()` 假設整組參數原子更新。
- 不直接把有 padding 的 C++ struct 當跨版本格式；明確欄位序列化、型別與長度。
- NVS 寫入失敗保留前版並回報，禁止默默清空 NVS 或繼續宣稱校準有效。遇到未知 schema 應安全停止或明確遷移。
- 不每半步、每秒或每分鐘寫 Flash。日常位置以 Uno 完成回報更新 ESP RAM；另在安全靜止時每 30 分鐘保存位置快照，與設定／校準保存共用節流。定期快照最多約 48 次／日，仍需依 Flash 與 NVS 配置評估耐久；沒有改變的內容不重寫。寫入期間先 DISARM，完成後確認原 session 狀態並重新 ARM，不建立新位置基準，也不影響 RTC。寫入計數供診斷。
- 若另選「每頁前／後寫 journal」模式，需先評估 NVS 分區、blob 大小、Flash 規格及磨耗；每天 1440 頁會至少 2880 筆寫入，不是本規格預設，也不能用 Uno EEPROM 的 100000 次數字套算 ESP32 壽命。

### 12.3 預設恢復流程

| 事件 | 預設結果 |
|---|---|
| 第一次開機 | 馬達不動，等待有效 RTC、機構設定與顯示校準 |
| 閒置時斷電 | RTC 可繼續計時；設定保留；下次開機仍要求確認實際顯示 |
| 半頁時斷電 | 位置 unknown；目視微調後重設顯示，不能自動採用目標位置 |
| NVS 提交中斷電 | 讀取最近完整 blob；沒有有效資料則安全待機 |
| RTC 電池失效／OSF=1 | 要求校時，不以 NVS 的舊 epoch 當目前時間 |
| 人工轉動機構 | 使用者必須重新校準；軟體無法自動偵測 |
| 軟體重啟／OTA 後 | 與其他重啟相同，預設重新確認位置 |

BLE 應同時顯示「最近保存位置及保存時間」和「本次執行位置」。快照最多可能落後設定的保存間隔，也可能因斷電／跳步與實物不同，故不能跳過重啟確認。

實際操作：手機讀狀態→必要時校時→目視檢查頁面是否完整落下→必要時微調→`set_display` 回報目前顯示→查看追趕預覽→`resume`／確認追趕。

這是可接受、可驗收的「斷電後恢復」，但不是免人工的絕對定位。若使用者日後要求完全自動恢復，需追加能唯一辨識機械週期的原點／位置感測方案。馬達輸出軸一圈若只占顯示週期的一小部分，單一軸原點並不能唯一辨識時分；FRAM 也無法解決斷電時的半步與漏步。

## 13. BLE v1 通訊規格

### 13.1 GATT 與安全

ESP32 內建 BLE 即可，不需 HC-05／HM-10。建議使用 NimBLE-Arduino 2.x，鎖定通過編譯與實測的精確版本；不要混用舊 Bluedroid 範例與不同 NimBLE 世代 callback。[NimBLE-Arduino 官方遷移與 API 說明](https://h2zero.github.io/NimBLE-Arduino/md__migration__guide.html)

裝置名稱：`FlipClock-XXXX`，XXXX 為裝置識別尾碼，不含金鑰。

| 特徵 | UUID | 屬性與內容 |
|---|---|---|
| Service | `b50c1000-7e6b-4e67-a540-a06c4fe1b201` | 本專案自訂服務 |
| Command RX | `b50c1001-7e6b-4e67-a540-a06c4fe1b201` | Write with response；接收命令 |
| Event TX | `b50c1002-7e6b-4e67-a540-a06c4fe1b201` | Indicate；回覆與完成事件，需訂閱 |
| Info | `b50c1003-7e6b-4e67-a540-a06c4fe1b201` | Read；固定短資料：協定版本、韌體版、boot_id |

最低正式安全要求：命令與完整狀態須經加密且驗證的配對連線，只允許已綁定手機控制。初次配對以 Uno UART 維修介面開啟 120 秒窗口，產生每台裝置獨立六位數 passkey 並僅在該次維修輸出顯示；手機輸入完成配對、保存 bond，之後無需 Uno。不可使用全機共用 `123456` 或假設 UUID 難猜等於安全。採 BLE Secure Connections 與合適的 IO capability，實作後用目標 Android／iOS 手機驗證實際配對方式及是否真的有 MITM 保護。

失去已綁定手機時，透過本地 UART 維修命令清除 bond、重新開窗口；不需要假設已有按鍵或螢幕。維修操作必須先停馬達。開發可提供明確的無驗證測試組態，但正式交付不得預設啟用；不能把 Just Works 說成具 MITM 防護。

### 13.2 封包、重送與佇列

使用 UTF-8 JSON Lines，每個完整 JSON 以 **實際 LF（0x0A）** 結束，不能只送兩個字元 `\` 與 `n`。欄位採 ASCII 名稱以簡化跨手機相容。

- 協定版本 `v=1`；每則請求有 `id`（uint32）及 `boot_id`（由 get_status／Info 取得）。示例中的 boot_id 只是示例，必須替換為實際值。
- 不依賴長 MTU：支援最低 ATT MTU=23，以每段最多 20 bytes 寫入／回傳。較大 MTU 可用 `MTU−3`，但必須能退回 20 bytes。
- 接收端可跨多次 write 重組一行，也可處理一次 write 內多行。最大單行 512 bytes（不含 LF），片段逾 2 秒未完成則丟棄並回 `E_FRAME_TIMEOUT`。
- 超長行進入丟棄直到 LF，不能把後半行當新命令；JSON 解析要在完整 bytes 重組後，不能對每段獨立解 UTF-8。
- 第一版只有一個控制連線、一則尚未回覆受理結果的請求及一個運動 job；accepted 後可受理 get_status／stop 等非衝突命令；其他移動命令回 `E_BUSY`。`stop` 是例外，可優先插入。
- Event TX 使用 indication 並遵守 BLE stack 背壓，一段確認後再送下一段。沒訂閱回覆通道時拒絕有副作用命令。
- 在同一 boot_id 內快取最近至少 16 個請求 id、payload 雜湊及結果。相同 id＋相同內容重送，回同一結果／job 狀態，**不得再走一次馬達**；相同 id 不同內容回 `E_ID_REUSE`。同一開機期間 id 單調增加，過舊已淘汰 id 回 `E_STALE_ID`，不重新執行。
- 重啟更換 boot_id；手機發現改變須重新讀狀態，不可盲目重送先前移動命令。斷線時清未完成 RX frame 與待處理命令；已開始自動翻頁可完成當前頁，人工 jog／追趕預設完成當前頁後暫停。
- 收到 Write response 只表示 BLE 傳輸接受；應用層 `accepted` 表示命令排入，`completed` 才表示軟體執行完成。不得將兩者混用。

### 13.3 命令與權限

| `op` | 主要參數 | 行為 |
|---|---|---|
| `get_status` | 無 | 分頁回覆時間、狀態、位置可信度、版本及錯誤 |
| `get_config` | 無 | 回覆 RAM 與保存版本、dirty flag，不含密鑰 |
| `set_time` | `utc_s`，整數秒 | 僅停止狀態；寫 RTC 並讀回；保持暫停，顯示位置不自動改成新時間 |
| `set_config` | `values` 物件 | 驗證整組範圍後更新 RAM；改比例／週期會使原位置基準失效；改時區要求重新預覽 |
| `save_config` | 無 | 停止時提交，成功後才回 `persisted:true` |
| `set_display` | `hour` 0–23、`minute` 0–59、`aligned:true` | 使用者目視確認實物；映射到 P 週期，重建基準及 r=0；不轉動、不校 RTC |
| `jog_steps` | `steps` −256…256，非零 | 暫停時微調；負值需允許反轉；完成後仍需確認顯示與對齊 |
| `advance_pages` | `pages` 1…60 | 經校準後人工前進整頁；共用同一補償公式 |
| `preview_sync` | 無 | 產生 plan_id、頁數、預估時間與是否需確認 |
| `resume` | `plan_id`、`confirm_large` | 只執行有效預覽；大型追趕需 true；之後正常自動走時 |
| `pause` | 無 | 當前頁完成後暫停 |
| `stop` | 無 | 停止後續步進；半頁位置 unknown；盡力關閉線圈 |
| `clear_fault` | 無 | 重新檢查故障原因；不得自動恢復位置可信度 |

出廠清除、清除 bond、開啟配對、改接腳、啟用 OTA 屬維修流程，不能偽裝成一般設定命令。`factory_reset` 至少要求本地維修介面及明確操作，且不得連帶覆寫仍有效的 RTC 時間。

設計範圍檢查：每頁步數 1…10000 半步、速率 10…900 half-steps/s、加速度 1…1000 half-steps/s²、穩定時間 0…5000 ms；這些是軟體防溢位範圍，**不表示整個範圍都能實機安全使用**。正式發布只允許不超過實測的速率上限。

### 13.4 範例

以下每個 JSON 各自再送一個 LF；`utc_s=0` 不是有效校時範例，手機必須使用目前 UTC 秒數。這裡用可讀的顯示／微調範例避免把文件日期誤燒入 RTC。

```json
{"v":1,"id":1,"boot_id":"a1b2c3d4","op":"get_status"}
{"v":1,"id":2,"boot_id":"a1b2c3d4","op":"set_display","hour":10,"minute":30,"aligned":true}
{"v":1,"id":3,"boot_id":"a1b2c3d4","op":"jog_steps","steps":4}
{"v":1,"id":4,"boot_id":"a1b2c3d4","op":"set_config","values":{"steps_per_page_u6":136000000}}
{"v":1,"id":5,"boot_id":"a1b2c3d4","op":"save_config"}
```

這些是獨立命令格式範例，不是建議操作順序；jog／改比例後須重新確認實際顯示。時間由手機取 UTC epoch seconds：原生程式將 Unix 毫秒除以 1000 取整數，發送前產生值，避免使用很早取得的時間。接收完整合法命令時寫入 RTC，回覆實際讀回 UTC 與處理結果，第一版校時驗收容許手機與 RTC 差 ≤2 秒。

```json
{"v":1,"id":3,"phase":"accepted","job_id":12}
{"v":1,"id":3,"phase":"completed","job_id":12,"steps_sent":4,"position_confidence":"unknown"}
{"v":1,"id":5,"phase":"completed","persisted":true,"config_generation":7}
{"v":1,"id":6,"phase":"error","code":"E_BUSY"}
```

最少錯誤碼：`E_JSON`、`E_VERSION`、`E_RANGE`、`E_AUTH`、`E_BUSY`、`E_NOT_CALIBRATED`、`E_TIME_INVALID`、`E_I2C`、`E_NVS`、`E_REVERSE_DISABLED`、`E_FRAME_TOO_LONG`、`E_FRAME_TIMEOUT`、`E_ID_REUSE`、`E_STALE_ID`、`E_BOOT_CHANGED`、`E_PLAN_STALE`。

Info 用短 ASCII 格式，例如 `1|1.0.0|a1b2c3d4`，第一版限制總長 ≤20 bytes，讓手機先取得實際 boot_id。完整狀態中 `coil_outputs_zero` 僅表示 Uno 回報控制輸出已為低，並非測得線圈電流為零。

狀態欄位最少包含：`state`、`rtc_utc_s`、`time_valid`、`utc_offset_min`、`display_index`、`position_confidence`、`moving`、`job_id`、`remaining_steps`、`fractional_remainder`、`config_generation`、`config_dirty`、`reset_reason`、`last_error`、`coil_outputs_zero`、`i2c_error_count`。若超過 512 bytes，分成多個有 `part`／`parts` 的獨立 JSON 行，同一查詢共用 id 與一致快照。

手機端不假定瀏覽器支援 BLE，尤其不把 Web Bluetooth 當成 iOS 通用方案。第一階段以能操作 GATT 的手機工具驗證；為了讓「自動取手機時間」容易使用，Codex 應另外交付一個最小可執行 BLE 客戶端，例如 Python＋Bleak（版本鎖定），完成掃描、訂閱、分包、校時、狀態與校準。它作為桌面開發／驗收工具；原生 Android／iOS 操作介面是後續項目，不要宣稱已交付手機 App。

## 14. ESP ↔ Uno I²C v1 協定

### 14.1 固定 32-byte frame

Uno AVR Wire 預設 buffer 為 32 bytes，因此每次 write 與每次 read **恰好 32 bytes**，不再加一個額外暫存器位址。此匯流排不用 JSON，也不依賴兩平台 C++ struct 的大小與排列。所有多位元組整數採 little-endian。

| Byte offset | 長度 | 欄位 |
|---|---|---|
| 0 | 1 | magic=`0xA5` |
| 1 | 1 | version=`1` |
| 2 | 1 | 命令 opcode；回覆則為 state |
| 3 | 1 | flags，未定義 bit 必須為 0 |
| 4–7 | 4 | session_id，uint32 |
| 8–11 | 4 | 命令 seq；狀態回覆為 job_seq |
| 12–15 | 4 | arg0，型別依 opcode |
| 16–19 | 4 | arg1，型別依 opcode |
| 20–23 | 4 | arg2，型別依 opcode |
| 24–27 | 4 | arg3，型別依 opcode |
| 28–29 | 2 | aux，uint16 |
| 30–31 | 2 | CRC-16/CCITT-FALSE，低 byte 在前 |

CRC 範圍為 byte 0…29；poly=0x1021、init=0xFFFF、refin=false、refout=false、xorout=0。標準自測字串 ASCII `123456789` 的 CRC 必須為 `0x29B1`。錯長度、magic、version、CRC、未定義 flags／欄位，均拒絕，不驅動馬達。

### 14.2 命令表

| Opcode | 名稱 | 參數／語義 |
|---|---|---|
| 0x01 | OPEN_SESSION | 新非零 session；seq=0；其餘 0。只在 unarmed 且無運動時建立；同 session 重送不得清空狀態 |
| 0x02 | ARM | seq>0；arg0=允許最高速率，arg1=最長 job 時間 ms，其餘 0；僅已握手且無故障時允許 |
| 0x03 | HEARTBEAT | 匹配 session、seq=0，其餘 0；僅更新 lease，不改工作結果／命令序號 |
| 0x10 | MOVE_STEPS | seq>0；arg0=int32 步數（非零、絕對值≤10000）；arg1=rate；arg2=acceleration；arg3=timeout_ms；aux=0 |
| 0x11 | STOP | seq>0；其餘 0；停止相位、關線圈、解除 armed；保留已執行步數 |
| 0x12 | DISARM | seq>0；其餘 0；僅 idle／done 可用，關線圈並撤銷 armed |
| 0x13 | CLEAR_FAULT | seq>0；其餘 0；確認外設／通訊條件後回 unarmed，不自行開始運動 |

第一版 rate 起測 200 steps/s，硬體測試上限不得超過設定的 cap；job timeout 設計上限 120000 ms。負步數只有編譯與配置均允許反轉才接受；不使用未驗證的反轉。所有未使用 arg 與 aux 固定 0。

`pause` 是 ESP 排程層行為：等當前頁 DONE 後送 DISARM；不要把 pause 變成另一種沒有定義的步進停止模式。

### 14.3 狀態回覆

ESP 對 0x12 直接 `requestFrom(...,32)` 取得最近完整快照，不需先寫讀暫存器指標。收到 32 bytes 後核對 CRC，再處理狀態；讀得太快時可能仍是上一快照，必須比對 `last_command_seq`，不能把舊 idle 當成新命令完成。

| 欄位 | 狀態中的意義 |
|---|---|
| byte2 state | 0=BOOT_UNARMED，1=IDLE，2=RUNNING，3=DONE，4=STOPPED，5=FAULT |
| flags bit0 | session_valid |
| flags bit1 | armed |
| flags bit2 | position_unknown（非絕對位置感測旗標） |
| flags bit3 | coil_outputs_zero；只表示控制輸出低，不是實測電流為零 |
| session_id | Uno 正在接受的 session；啟動為 0 |
| job_seq | 正在執行或最近一個運動的 seq；從未運動為 0 |
| arg0 | int32 已執行的帶方向步數 |
| arg1 | uint32 尚餘步數絕對值 |
| arg2 | uint32 最近處理完的非 heartbeat 命令 seq，接受與拒絕皆回報 |
| arg3 | uint32 Uno uptime_ms，可 rollover |
| aux low byte | 最近命令錯誤碼 |
| aux high byte | phase index 0…7；尚未定義為 0xFF |

最少錯誤碼：0=OK、1=BAD_FRAME、2=BAD_SESSION、3=NOT_ARMED、4=BUSY、5=RANGE、6=SEQ_REUSE、7=STALE_SEQ、8=LINK_TIMEOUT、9=MOTION_TIMEOUT、10=RX_OVERFLOW、11=REVERSE_DISABLED、12=INTERNAL_FAULT。CRC 壞掉時不得信任 frame 裡的 seq，可僅更新錯誤計數，不回覆假的已處理序號。

### 14.4 冪等、重試與 session

- ESP 每次新控制 session 產生非零隨機 uint32 session_id；這是識別運動世代，不是安全認證密鑰。
- 非 heartbeat／OPEN_SESSION 命令 seq 從 1 單調遞增，不允許繞回；即將溢位時先停止、解除 armed、建立新 session。
- Uno 保存最近至少 4 筆可變動狀態命令的完整 30-byte 有效負載與處理結果，不能只比較 16-bit CRC 當唯一內容識別。相同 seq＋相同內容回原結果；相同 seq 不同內容拒絕；低於已處理水位且已淘汰的舊 seq 拒絕，不重跑。
- 一個新的 OPEN_SESSION 只能在已解除 armed 且停止時進行；同 session 的 OPEN_SESSION 重送只回現況，不能清 job／序號水位。新 session 不代表機械位置變可信。
- 正常約每 50 ms 輪詢。命令在 200 ms 內未有應用層回報，可重送同 frame，最多 3 次；仍不確定時停止後續排程、讓 lease 失效並要求重新確認，不用新 seq 猜測重跑。
- DONE 與 executed_steps 保持到下一個 MOVE 接受，heartbeat／讀狀態不得清掉。ESP 記錄已提交 job_seq，確保重複 DONE 只更新一次頁數與 r。
- MCU 重啟會丟失 RAM 去重表，所以 Uno 啟動 unarmed 且 session=0 是必要條件。無 NVS／感測器配合時，不宣稱跨任意斷電仍能 exactly-once 機械執行。
- 兩槽固定 RX queue 足夠第一版；滿時回錯誤、不覆寫未處理命令。STOP 應在主迴圈優先處理，驗證延遲；未通過完整 CRC 的資料不能觸發運動或刷新 lease。

## 15. 網路時間、RTC 與 BLE 的優先規則

### 15.1 正常時間來源

ESP32 以 2.4 GHz Wi-Fi 連網，SNTP 校正軟體 UTC 與 DS3231；RTC 提供無網路時的基準。Uno 不連網也不直接讀 RTC。使用 Espressif／Arduino 正式時間 API，不能把開機 `millis()` 當絕對時間。[Espressif System Time／SNTP](https://docs.espressif.com/projects/esp-idf/en/stable/esp32/api-reference/system/system_time.html)

- 開機先驗證 RTC；即使 Wi-Fi 不通，RTC 有效且位置經確認仍可走時。網路不能成為日常運轉的阻塞前提。
- Wi-Fi SSID／密碼透過本地 UART 維修輸入，或後續已配對加密 BLE 設定流程；不能硬寫個人憑證到原始碼／Git，也不開無密碼設定 AP。
- SNTP 伺服器名稱可配置，預設最多三個合理來源並提供逾時／退避。每次成功校時紀錄來源、UTC 與偏差；例如每 6 小時重新同步，失敗只重試連網，不反覆轉馬達。
- 只有實際收到有效 SNTP 同步通知、日期範圍合法，才標記網路時間有效；不能僅以系統 year>1970 判斷收到網路校時。
- 非初次校時時，若新來源相對有效 RTC 差超過 5 分鐘，先暫停與回報要求確認。小修正也先在無運動時套用，再重新預覽，不可突然反轉或補整圈。
- 若 RTC 原本無效，可採有效網路時間建立 RTC；機械位置仍需另外確認。任何來源只修時間，不能直接把 `display_index` 改成目前時刻。
- 使用 UTC 存 RTC；時區只影響顯示。SNTP 的夏令時間／本地時區設定不得再被重複加到 RTC。
- SNTP 通常沒有可依賴的來源認證；本專案以日期範圍、跳變門檻與操作者確認限制錯誤時間的機械影響，不宣稱時間來源具安全認證。

### 15.2 手動校時與自動模式

BLE `set_time` 受理後設 `auto_time=false`，避免立即被 SNTP 覆寫；時間更新仍需讀回 RTC。`set_config` 另支援 `auto_time`，重新開啟時應預覽與說明將以網路時間同步。此選擇可透過 `save_config` 保存。

狀態新增 `time_source`（rtc／sntp／ble_manual／invalid）、`last_sync_utc`、`last_sync_offset_s`、`wifi_state`、`auto_time`。不回報 Wi-Fi 密碼。若 RTC 失聯，按第 8 節安全停止自動排程，不能以網路時間正常掩蓋硬體故障。

## 16. ESP 與 Uno 的建置、燒錄、維修要求

### 16.1 可重現環境

交付兩份獨立 firmware，使用 Arduino C++ 與相同的協定定義／測試向量：

```text
firmware/esp32_clock/       ESP32 主控
firmware/uno_motor/         ATmega328P 運動控制
shared/protocol/            wire-format 規格、編解碼與 CRC 測試向量
tools/                     BLE／序列驗收客戶端與建置腳本
tests/                     主機端規劃器、協定、重送與斷電模擬
docs/                      接線、兩種模式切換、校準、測試紀錄
```

- ESP：Arduino IDE 2.x／Arduino CLI，Espressif 官方 board package；選擇 `AI Thinker ESP32-CAM`，常見 FQBN 為 `esp32:esp32:esp32cam`，以安裝版本的 board list 確認。classic ESP32、實測 Flash 容量（常見 4 MB）、保守 40 MHz Flash 起測。不可預設所有相容板容量相同。
- Uno：官方 Arduino AVR Boards，板型 Uno，常見 FQBN `arduino:avr:uno`；16 MHz ATmega328P。不能因接上 Uno COM 埠就用 Uno FQBN 編譯 ESP 程式。
- 鎖定精確 core／library／CLI 版本；ESP 選通過測試的 Arduino-ESP32 3.x 穩定版及相容 NimBLE 2.x，不能混用 2.x core 的舊 API。若環境需其他版本，先報告兼容原因並重驗，不寫「永遠使用最新版」。
- ESP 依賴：Wire、Preferences、WiFi、time／SNTP，RTC 可用 RTClib，BLE 可用 NimBLE-Arduino；依賴版本、來源與授權納入 manifest。Uno 以 Wire＋AVR 內建功能為主，不導入大型 JSON 或 BLE 函式庫。
- Uno SRAM 僅 2 KB，需提交編譯記憶體報告及最壞堆疊估算，固定長度 buffer、不用動態 `String`。靜態 RAM 建議控制在約 1.2 KB 內，留足堆疊並實測，不把編譯成功等同無溢位。
- 分別提供編譯與上傳命令／腳本、輸出韌體 SHA-256、版本號及 protocol version。實際 COM 由使用者環境列舉，不寫死不存在的埠。
- Uno 不需要燒 ArduinoISP；ESP 韌體由 PC 編譯與 esptool 上傳，Uno 板載 USB UART 作傳輸，並非 Uno 自行儲存 ESP 映像再燒入。

參考：[Arduino-ESP32 安裝](https://docs.espressif.com/projects/arduino-esp32/en/latest/installing.html)、[2.x→3.x 遷移](https://docs.espressif.com/projects/arduino-esp32/en/latest/migration_guides/2.x_to_3.0.html)、[Uno R3 官方手冊](https://docs.arduino.cc/resources/datasheets/A000066-datasheet.pdf)。

### 16.2 三個明確操作模式

| 模式 | Uno RESET→GND | Uno D0/D1 到 ESP | ESP GPIO0→GND | 馬達 |
|---|---|---|---|---|
| 刷 ESP 韌體 | 接上，328P 持續 reset | 經 BSS138 接好 | 接上並 reset ESP | 斷電 |
| 刷 Uno 韌體 | **移除** | **拆除** | 移除 | 斷電 |
| 正常雙主控 | **移除** | **拆除** | **移除** | 驗證後供電，由 Uno D8–11 控制 |

刷 ESP 的詳細方向、電源、電平裕量見第 5 節。刷完 ESP 再 reset 正常啟動；刷 Uno 時選 Uno 板型，透過其 USB 正常上傳。Uno 控制馬達的程式不會因只是拉 RESET 接地而被清除；完成 ESP 燒錄後移除跳線即可重新執行。若要更新 Uno 程式則另行正常上傳。

正常的 A4/A5 I²C 線與刷 ESP 用的 D0/D1 是不同接線。刷寫時可先斷開 I²C 支路做隔離排障；恢復時按接線表重接。每次切模式先停止裝置並斷馬達電源，不允許一邊刷 ESP 一邊讓 Uno 維持馬達工作。

### 16.3 選配 OTA

OTA 僅針對 ESP32-CAM，**不會順便更新 Uno**。第一版可不做；首次仍用 Uno UART 燒入。如果日後加入：

- 首次就選擇符合實際 Flash 容量、具有兩個 app slot 與 otadata 的分區，提交 CSV 與各區邊界檢查。某些大 app 無 OTA 分區不能直接用；韌體必須小於每個 slot，CI 檢查大小。
- 更新前 pause、等 Uno 停止、DISARM 並確認控制輸出全低，再進 OTA。更新後位置重新確認，不自動沿用前次工作。
- Wi-Fi 更新需認證與受控維修窗口，不把無保護更新服務長期暴露；憑證不硬寫。
- 斷線／斷電不得覆蓋唯一可啟動映像。若聲稱自動 rollback，必須確認 bootloader 與配置真的支援並實測，不能只因有兩個 slot 就宣稱可回滾。
- NVS schema 與舊／新韌體相容；不得用 OTA 偷改分區造成資料清除。UART 燒錄救援流程保留。

[Espressif 分區說明](https://docs.espressif.com/projects/arduino-esp32/en/latest/tutorials/partition_table.html)

## 17. Codex 分階段開發與交付

各階段皆可先做軟體工作；需實物的結果只能記錄待測，不能由模擬冒充實測。

| 階段 | 內容 | 通過條件 |
|---|---|---|
| P0 盤點與建置 | 確認板型／供電／RTC 電池；兩個 firmware 空殼、依賴鎖定、協定測試向量 | 兩板程式分別編譯；文件標明硬體待確認 |
| P1 Uno 刷 ESP | 只接下載必要線，ESP log＋BLE advertising；馬達不供電 | 連續 5 次完整上傳與驗證，模式切換正確 |
| P2 Uno 馬達單機 | Uno D8–11 半步，低速正向 jog、pause／stop、看門狗 | 不堵塞控制；reset 期間無意外轉動；相序與方向記錄 |
| P3 雙板 I²C | 固定 32-byte frame、CRC、握手、重送、lease；RTC 並行讀取 | 重複 MOVE 不重走，失聯停機，單板重啟安全 |
| P4 RTC 與 NVS | UTC、OSF、設定 A/B blob、掉電讀回 | 設定保留；RTC 無效不動；未校準不動 |
| P5 規劃器與校準 | 每頁步數、小數補償、週期、目視位置、追趕 | 跨整點／午夜正確，校時倒退不亂跑 |
| P6 BLE＋Wi-Fi | 分包／配對、手機校時、網路同步、來源優先規則 | 最低 MTU 可用；斷網仍可 RTC 走時；命令無重複副作用 |
| P7 耐久與故障注入 | 斷電、單板 reset、CRC 壞包、馬達負載、72 小時走時 | 完成第 18 節實機測試並記錄限制 |
| P8 選配 | OTA、感測器或其他擴充 | 各自另列硬體與驗收，不能阻塞基礎版交付 |

Codex 必須交付：兩份完整原始碼、版本鎖定 manifest、建置／燒錄腳本、各板韌體檔、接線與模式切換文件、協定與 CRC 測試向量、BLE 驗收工具、測試結果、未解決問題。每次里程碑說明「已編譯／已模擬／已實機」的區別，不宣稱尚未操作的硬體已測過。

## 18. 驗收測試矩陣

### 18.1 自動化／主機端測試

| 編號 | 測試 | 必須結果 |
|---|---|---|
| S01 | q/r 定點補償，單頁累加與整段比較 | 相同步數與餘額；長期數值誤差 <1 半步（不含機械誤差） |
| S02 | 12／24 小時、整點、午夜、跨日、閏日 | 合法索引；UTC 正常遞增不誤判倒退 |
| S03 | 校時 −1 分鐘、＋10 分鐘、＋2 天、改時區 | 暫停／預覽／限額生效，不盲目補整圈 |
| S04 | CRC 標準向量、每 byte 翻轉、錯長度／版本 | 正確接受／拒絕，壞包無馬達副作用 |
| S05 | MOVE 重送、DONE 重讀、相同 seq 不同內容 | 不重走、不重複提交 r 或顯示索引 |
| S06 | 去重 cache 淘汰後舊 seq、seq 將溢位 | 拒絕舊命令；安全換 session |
| S07 | Uno／ESP 在 accepted、半程、DONE 未讀時各自重啟 | 位置 unknown，不自動重播不確定命令 |
| S08 | NVS blob 寫入中斷、CRC 錯、舊 schema、空 NVS | 只讀完整合法版本；失敗安全待機 |
| S09 | BLE 20-byte 分段、合併行、UTF-8 邊界、超長與 timeout | 正確重組／拒絕，無溢位，stop 可處理 |
| S10 | AVR 16-bit int／32-bit uptime rollover／大數運算 | 不溢位或錯方向；明確固定寬度型別 |
| S11 | 網路同步與手動時間衝突、離線重連 | auto_time 規則生效，RTC 不被重複加時區 |

### 18.2 實機測試

| 編號 | 測試 | 必須結果／記錄 |
|---|---|---|
| H01 | 三種操作模式切換 | RESET／GPIO0／D0D1 狀態符合表；正常時 Uno 不被維持 reset |
| H02 | Uno 刷 ESP，115200 起測 | 5 次完整上傳與校驗成功；如降速需記錄；電氣裕量問題不能靠降速掩蓋 |
| H03 | I²C 電壓與啟動 | 低壓側約 3.3 V，高壓側約 5 V；掃到 0x12／0x68；無 5 V 灌入 ESP |
| H04 | 兩板冷啟動 30 次，先後供電順序測試 | 無非預期轉動；未通電板不被信號反向供電 |
| H05 | Uno 輸出相位與低速空載 | 相序、方向正確；最多一／二線圈；輸出關閉功能正確 |
| H06 | 負載加速＋Wi-Fi＋BLE | 無 brownout／reset／已知漏頁；記錄板端電壓、電流、溫度與合格速率 |
| H07 | 斷開 SDA／SCL、關閉 ESP | Uno 在 1.6 秒內停止相位並輸出全低，回復後不自動續跑 |
| H08 | 正常 stop／pause | stop ≤100 ms；pause 完成當頁再停；半頁 stop 位置 unknown |
| H09 | Uno 單獨 reset、USB DTR reset | 輸出安全，ESP 撤銷位置可信度；不重播未完成工作 |
| H10 | 移動前、半頁、完成後、NVS 保存時切斷總電源 | 重啟保留可用設定／RTC，要求確認位置，不採用舊目標冒充現況 |
| H11 | RTC 斷主電源 24 小時 | 電池路徑已確認安全；復電時間連續且 OSF 正常；結果與參考時間對照 |
| H12 | 無電池／OSF=1／RTC 拔除 | 顯示 time_invalid，禁止自動運轉，可經受控校時復原 |
| H13 | BLE 真機配對與拒絕未授權寫入 | 實際 Android／iOS 系統版本記錄；未配對不能移動或改設定 |
| H14 | BLE 重送、斷線、最低 MTU | 不重複 jog；長工作可停；重新連線可讀正確狀態 |
| H15 | 斷網 24 小時後恢復 | RTC 維持走時；網路恢復不觸發突發大幅移動 |
| H16 | 完整機械週期及 72 小時走時 | 無觀察到的漏頁／重頁／半頁；跨整點正常；分開記錄 RTC 誤差與機械誤差 |
| H17 | 校準後斷電再開，輸入實際顯示 | 預覽追趕量正確，確認後到目前時間，超限不自動跑 |
| H18 | 選配 OTA 期間斷網／斷電 | Uno 保持停止；ESP 有已驗證救援路徑；位置重新確認 |

校時目標：BLE／網路同步後，在良好鏈路與實際設備上 RTC 與參考時間差 ≤2 秒。常態分鐘邊界開始移動目標 ≤1 秒；完成落頁延遲另計並記錄。這些是驗收目標，不是本文已量測結果。長期 RTC 漂移應依實際晶片版本、溫度與參考時鐘判讀，不用一天目視觀察宣稱永久零誤差。

## 19. 安全與故障處理要求

- 先斷電再插拔馬達／RTC 電池／轉換器；不要在帶電時用手插拔五線馬達接頭。
- 確認 5 V／12 V 馬達版本；不可用提高電壓掩蓋錯相序、阻力或漏步。
- ULN2003 不是限流型步進驅動器，不得用輸出腳的最大額定值當整塊板可同時供應的電流。
- 機構卡住不一定能由軟體察覺。微調與追趕時避免手指進入夾點；需要可立即拔除／關閉的馬達電源，不能只依賴手機 stop。
- 若斷電後齒輪會回轉或重力會帶動機構，關閉線圈不代表實物固定；位置一律重新確認。持續保持電流需另做溫升與機構評估。
- 只有完整受理的 matching-session heartbeat 刷新 lease；垃圾包、單純 I²C 活動不能讓馬達無限保持可執行狀態。
- 驗收不得把 ACK 當作已翻頁，不得把 NVS 記錄的 target 當成真正位置，不得把多主控當成自動冗餘容錯。
- 所有電源與電池處理依本文核對後施工；若有不明模組充電路徑，先留空電池座，不猜元件標號。

## 20. 給 Codex 的執行摘要與來源紀錄

本專案固定使用「ESP32 管理時間／網路／BLE／設定、Uno 管理馬達」架構；ESP 的首次與救援燒錄透過 Uno R3 板載 USB UART。以 I²C 0x12 固定 32-byte 協定連接兩板，RTC 0x68 在 ESP 3.3 V 側。BSS138 同時提供正常 I²C 的兩路電平轉換，另兩路只在刷 ESP 時使用。不要把正常運轉接法與燒錄接法混用。

先完成 P0–P3，再整合時間與儲存。不能任意加入未確認持有的硬體，也不能因目前有 MCP23017 就強制串進馬達路徑。沒有原點感測器時採 SAFE_RECONFIRM；預設停機、驗證、明確完成回報與冪等命令是必做功能。

來源查核日期：2026-10-31。原始 snippet raw 檔已下載比對，SHA-256 見第 2 節；Uno R3 與 ESP32_CAM V1.6 原理圖已做圖面檢查；使用者上傳的電平轉換模組圖片已查看，但不憑該圖片推定 RTC 型號或電池電路。各技術依據已在對應段落提供原始連結，主要來自 Arduino、Espressif、Microchip、Analog Devices、TI、Nexperia，以及 RTC 模組的第一手線路分析。

本文件未代替實物量測，未執行兩板韌體編譯或馬達實測；這些屬上述 Codex 開發與驗收階段。最終測試報告必須清楚區分來源已核對、軟體已測與硬體待測。
