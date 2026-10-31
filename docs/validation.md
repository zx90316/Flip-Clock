# 驗證與交付紀錄

本紀錄區分「已編譯／已模擬／實機待測」。已實際連接 COM3 的 Uno、完成燒錄校驗及 UART 安全待機診斷；其他裝置與馬達尚未實測。沒有以原參考專案回報代替本版驗收。

## 已編譯

| 目標 | 核心／板型 | Flash 程式用量 | 靜態 RAM |
|---|---|---:|---:|
| Uno R3 | Arduino AVR 1.8.8，arduino:avr:uno | 9,026／32,256 bytes | 869／2,048 bytes |
| AI-Thinker ESP32-CAM | Arduino-ESP32 3.3.12，huge_app、40 MHz | 1,219,546／3,145,728 bytes | 95,192／327,680 bytes |

ESP 靜態 RAM 數字不包含所有執行時 Wi-Fi／BLE heap 配置，不是最低 free heap 的實測。目標 Flash 為 4 MB，容量及 PSRAM 實物狀態待確認。

原始編譯輸出：[Uno](uno_motor-build.txt)、[ESP32](esp32_clock-build.txt)。Uno 官方核心 new.cpp 有未使用參數警告，專案韌體編譯通過。Uno 正式映像維持官方 LTO；[獨立非 LTO 堆疊分析](uno-stack.md)列出單一 frame 與保守工程預算，實機高水位仍未測。未採用非 LTO 分析映像作交付韌體。

`dist` 含兩板可燒錄檔、ELF、ESP 分區／bootloader 及 SHA-256 manifest。ESP `.merged.bin` 是完整 UART 燒錄映像，`.ino.bin` 是應用程式映像；交付腳本使用官方上傳配方，不把兩者混用。**不支援 OTA。**

## 已通過的主機驗證

執行 `python tools/build.py test`。實際輸出見 [host-tests.txt](host-tests.txt)：

- C++ 共用核心：22,055 個檢查，其中大部分是數值／位元翻轉迴圈；這不是 22,055 項獨立硬體測試。
- C++ 實際 ESP app／supervisor／link／RTC／NVS 程式搭配模擬外設：45 個檢查。
- Python BLE 客戶端 7 項、VS Code 操作工具 6 項測試。

覆蓋 CRC 標準及獨立 wire 向量、全 frame 每 bit 翻轉、非法 flags、負數及範圍拒絕、原 seq 重送、內容重用／cache 淘汰、DONE 不重複提交、STOP 中途保留步數、失聯及逾期 heartbeat 不能救回工作、millis/micros rollover、相位連續、重啟不接受舊 MOVE。

規劃器覆蓋 q/r 單頁與整段一致、最大整數值、720／1440、午夜、2000–2099 各月末及閏日、過期預覽、重複提交及重新確認位置。保存格式覆蓋截斷、逐 byte 破壞、A/B 選擇及空儲存；實際 Store 模擬另覆蓋讀回、同值不重寫、五秒節流、寫入失敗保留舊代。

應用流程模擬覆蓋校準後多頁移動、pause 完成當頁、stop 使位置失效、Uno 重啟／斷線、手動校時關閉 auto_time、大幅 SNTP 修正等待確認，以及 callback 對未驗證／未訂閱連線的寫入閘門。BLE 桌面工具覆蓋 20-byte 分包、跨 UTF-8 邊界、三段狀態、byte-identical 重送、重啟不送移動、id 跨程式重開保持單調及命令長度上限。

模擬沒有模擬 RF、手機作業系統配對畫面、實際 Flash 掉電行為、電氣 I²C 拉伸／雜訊、機械阻力或棕斷，因此不替代這些實測。

## 階段狀態

| 階段 | 目前狀態 | 尚缺 |
|---|---|---|
| P0 | 兩板完整程式、版本及向量已建置 | 板型、Flash、馬達、RTC 電池實物盤點 |
| P1 | ESP 安全開機及 BLE 程式已編譯 | Uno UART 五次完整上傳與電平裕量量測 |
| P2 | Uno 核心及動作／停機模擬通過 | 空載相序、方向、watchdog／bootloader、重置測試 |
| P3 | 32-byte 協定、去重、lease 與重啟模擬通過 | 真實雙板 I²C、斷線及 STOP 延遲量測 |
| P4 | RTC UTC 與 A/B blob 程式及故障模擬通過 | RTC 電池保持、真實 NVS 掉電與壽命評估 |
| P5 | 定點規劃、預覽、完成提交與校準流程已實作 | 機構實際 q、720／1440 週期、整點與完整週期驗收 |
| P6 | BLE／Wi-Fi／SNTP 已整合及編譯、桌面工具可執行 | Android／iOS 配對、MITM／SC、最低 MTU、24 小時離線恢復實測 |
| P7 | 故障注入工具與表格備齊 | 負載、實際斷電及 72 小時走時 |
| P8 | OTA／感測器未啟用 | 選配另立設計及驗收 |

## 實機待測

Uno 單板燒錄／校驗及安全待機已實測；H01–H17 的完整驗收條件仍**尚未完成**，H18 OTA 不適用本版。詳細期望依原工程規格第 18 節，填寫 [hardware-acceptance.csv](hardware-acceptance.csv)。必要紀錄包含接線模式、韌體 SHA、板型、電壓／電流／溫度、測試參數、手機 OS 與 BLE 工具版本、實際延遲及成功／失敗證據。

尤其要測：30 次冷啟動無意外轉動、5 次 Uno 刷 ESP 成功、低壓側無 5 V、失聯 1.6 秒內關輸出、stop ≤100 ms、實機安全拒絕未授權寫入、RTC／NVS 掉電、完整機械週期與 72 小時漏頁／重頁。這些數字是目標，不是已量測結果。

## 已知限制與後續

- 無原點或絕對位置感測，DONE 只代表送完相位，無法證明機械到位；重啟、stop 或不確定交易後須目視確認。
- 目前正式映像正向限定、速率 cap 200，未經實機調校，不承諾該速率在負載下合格。改方向／反轉及提高 cap 必須另做配置與驗收。
- BLE 安全設定已編譯並由閘門模擬檢查，尚未以真機／封包驗證配對方式、SC 降級拒絕、bond 復連與 RF 背壓。
- SNTP 採一般未認證時間來源；日期、跳變及明確確認限制機械影響。每次校時後保守保持暫停，需重新 preview／resume。
- 交付建置腳本以目前 Windows 環境驗證；其他 OS 需放置相同版本 Arduino CLI 並驗證編譯流程。桌面工具沒有原生手機 UI。
- 參考分支後續若更新，需先比較硬體與協定；不直接覆蓋本版接線或採用其多輪字元／12 V 參數。

已建立獨立公開 Repo；Uno 已燒錄／校驗，尚未啟動馬達。詳細實物進度見 hardware/progress.md；整體硬體驗收仍待依表執行。
