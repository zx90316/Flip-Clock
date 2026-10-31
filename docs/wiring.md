# 接線、電源與維修模式

本表以**已確認為 5 V 的單顆 28BYJ-48**為前提；若銘牌是 12 V，先停止接電並修訂電源設計。ESP32-CAM 使用 AI-Thinker classic ESP32，不套用 S3／C3。施工前核對 RTC 電池充電支路、電源規格及 BSS138 A/B 側。

## 正常運轉

| 訊號 | ESP／3.3 V 側 | BSS138 | Uno／5 V 側 |
|---|---|---|---|
| SDA | GPIO13＋DS3231 SDA | A2 ↔ B2 | A4／SDA |
| SCL | GPIO14＋DS3231 SCL | A3 ↔ B3 | A5／SCL |
| 參考電源 | ESP 3V3、DS3231 VCC | VCCA／VCCB | Uno 5V |
| 地 | ESP／RTC GND | 共同 GND | Uno／ULN2003 GND |

ESP 是唯一主端，100 kHz；Uno 從端 0x12，RTC 0x68。RTC 的 SQW／32K／RST 留空。兩側各自上拉到各自電源；量測現有上拉並聯值及線路高低電位。不能把 Uno 5 V I²C 直接接到 ESP。正常使用不插 microSD、不初始化相機、不接 D0／D1 燒錄線。

| Uno 腳 | ULN2003 |
|---|---|
| D8 | IN1 |
| D9 | IN2 |
| D10 | IN3 |
| D11 | IN4 |
| GND | GND |

馬達正端直接接外部穩壓供電分支，不經 Uno／ESP 板載穩壓器或走線。確認 ULN 模組 COM／箝位二極體路徑。確認 IN1–4 已有可靠下拉，沒有則盤點／補各約 10 kΩ 下拉，以降低 reset 期間的意外通電。

穩壓 5 V／2 A 僅作初步設計起點；ESP32-CAM 接 **5V 腳**，RTC 接 3V3，板端量測 Wi-Fi＋BLE＋馬達動作時電壓及溫升。Uno 可用合適 USB 電源入口或經確認的穩壓 5V 腳；5 V 不能接 VIN 期待正常穩壓。馬達回流直接回電源，控制板共地。

連電腦 USB 前斷開 Uno 外部 5 V 正電源路徑，不將兩個 5 V 輸出並聯。不用 Uno 3.3 V 腳供 ESP；不要讓未通電板被信號反向供電。裝拆接頭、RTC 電池及轉換器前都先斷電。

## 三種模式

| 模式 | Uno RESET→GND | Uno D0／D1 到 ESP | ESP GPIO0→GND | 馬達供電 |
|---|---|---|---|---|
| 刷 ESP | 持續接上 | 經電平轉換接上 | 接上，重置 ESP 進下載模式 | 關閉 |
| 刷 Uno | 移除 | 拆除 | 移除 | 關閉 |
| 正常運轉 | 移除 | 拆除 | 移除 | 驗證後啟用 |

刷 ESP 時的 UART 方向，依標準 Uno R3 的 USB UART 旁路接法：

| 起點 | 電平轉換 | 終點 |
|---|---|---|
| Uno D0/RX（16U2 TX） | B0 → A0 | ESP U0R／GPIO3 |
| ESP U0T／GPIO1 | A1 → B1 | Uno D1/TX（16U2 RX） |
| Uno 5V | 轉換器高壓側參考 | VCCB |
| ESP 3V3 | 轉換器低壓側參考 | VCCA |

ESP 另由外部穩壓 5 V 供電，兩側共地。Uno RESET 與 ESP RESET 不綁在一起；Uno 的 328P 持續 reset，ESP 獨立按 RST。相容 Uno 若不是 16U2，須重新核對電路。

UART 先以 115200、短線起測。官方 Uno UART 路徑有約 1 kΩ 串聯電阻，會和 BSS138 上拉影響低電位；先驗證電位與邊緣，完成五次完整上傳／校驗。降低 baud 不能修正不合格的邏輯低電位。若不符門檻，停止使用該轉換配置，改用經驗證的 UART 電平方案。

完成 ESP 燒錄後移除 GPIO0→GND 並重置 ESP；要恢復雙主控時，另移除 Uno RESET→GND 及 D0／D1 信號線，再恢復正常 I²C 接線。拉 Uno RESET 不會清除原 Uno 韌體。

## RTC 電池與機構待確認

DS3231 晶片沒有充電器，部分模組另有充電支路。拿下電池、斷電後確認 VCC 到電池正端的電路；**不可讓不可充電 CR2032 接在會充電的路徑上**。不能單靠改供 3.3 V 就宣稱安全，也不盲拆未知板上的 R／D 元件。無法確認時先留空電池座，只做通電測試。

尚須確認每頁是否一分鐘、週期 720／1440、正向方向、馬達電壓、插座線序、電源及負載。軟體送完步數不代表機構翻頁成功；卡頁、漏步、人工轉動都可能無法偵測。現場保留可立即關閉的馬達電源，手指避開夾點。

原始電氣依據與更多細節見 [工程規格第 4–8 節](engineering-spec.zh-TW.md)，包括 [Uno R3 原理圖](https://docs.arduino.cc/resources/schematics/A000066-schematics.pdf)、[BSS138 I²C 轉換原理](https://assets.nexperia.com/documents/application-note/AN10441.pdf) 與 [DS3231 datasheet](https://www.analog.com/media/en/technical-documentation/data-sheets/ds3231.pdf)。
