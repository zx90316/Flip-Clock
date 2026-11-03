# 協定與資料格式

BLE 與保存格式。實作在 [FlipStorage.h](../shared/protocol/src/FlipStorage.h) 與 [FlipStream.h](../shared/protocol/src/FlipStream.h)，不用 C++ 結構記憶體排列傳送。

## BLE v1

| 項目 | UUID 尾段（共同格式 b50c10XX-7e6b-4e67-a540-a06c4fe1b201） | 屬性 |
|---|---|---|
| Service | XX=00 | 自訂服務 |
| Command RX | XX=01 | Write with response、加密及驗證 |
| Event TX | XX=02 | Indicate；未訂閱不受理寫入 |
| Info | XX=03 | Read，`1|0.2.0|boot_id`，≤20 bytes |

UTF-8 JSON Lines，以實際 LF 結束；最大每行 512 bytes，最低 MTU 每段 20 bytes。完整 bytes 收齊才解析 JSON；超長行丟棄至 LF，未完成行逾 2 秒丟棄。Indication 等確認後才發下一段，背壓／佇列滿時暫停及斷線，避免遺失結果後繼續排程人工工作。

所有 JSON 命令有 `v:1`、單調 uint32 `id`、正確 `boot_id`、`op`。16 筆 cache 比對完整請求內容及保存結果，相同 id 不同內容 E_ID_REUSE，淘汰舊 id E_STALE_ID。跨 BLE 連線仍保留同一開機的去重表；重啟則換 boot_id，客戶端停止盲目重送。

`get_status` 以三行 part/parts 回同一次查詢快照，單行≤512 bytes；cache 保存整組回覆。設定、即時位置與保存快照分開。`coil_outputs_zero` 只表示 ESP 的控制輸出為低，並非電流量測。

命令依原規格：get_status、get_config、set_time、set_config、save_config、set_display、jog_steps、advance_pages、preview_sync、resume、pause、stop、clear_fault；另有 `confirm_time(utc_s)` 確認尚待採用的大幅 SNTP 修正。移動／保存先 accepted，真正結束才 completed；已完成頁數不因取消而回滾。人工多頁暫停的完成回覆含 requested_pages、pages_completed、paused，不宣稱剩餘頁數已走完。

只允許單一控制連線；新手機須 UART 開配對窗口，使用每次隨機六位數 passkey、DisplayOnly、bonding、MITM、Secure Connections only、16-byte 加密金鑰。NimBLE 2.5.1 的自動舊 bond 替換由可重現補丁改為拒絕；清 bond 只走本地維修。實際手機是否依預期配對、拒絕未授權寫入仍須 H13 驗收，模擬不能代替無線安全實測。

## A/B 保存 schema 1

設定 blob 固定 80 bytes，不保存 ABI padding，LE；CRC32/IEEE 對 0–75，存在 76–79。namespace `flip-clock`，key `a`／`b`，generation 不繞回。選最新完整合法 slot，寫較舊 slot 並讀回；未知／壞格式且無可用 slot 時安全待機，不自動抹除。

| 位移 | 內容 |
|---|---|
| 0–11 | FCLK、schema uint16、長度 uint16、generation uint32 |
| 12–19 | steps_per_page_u6 uint64 |
| 20–35 | cycle、rate、accel、settle、offset(int16)、maxPages、maxSeconds、checkpoint，各 uint16 |
| 36–39 | mechanics、reverse、autoTime、direction(int8) |
| 40–55 | snapshot valid、phase、display uint16、r uint32、UTC int64 |
| 56 | board profile=1；固定 SAFE_RECONFIRM、release_coils=true |
| 57–61 | snapshot generation uint32、source byte（0 無／1 使用者確認／2 開迴路） |
| 62–63 | snapshot cycle uint16，保留該歷史位置的機械週期 |
| 64–65 | 舊版步數偏移 trim int16（相容保留；新版手動進步不寫入） |
| 66–75 | 保留 0 |
| 76–79 | CRC32 |

變更先在 RAM，save_config 才保存。未變更的設定及位置不因時間更新而重寫；最短保存節流五秒，定期快照預設 30 分鐘。寫入期間馬達不動。位置未知時保留先前歷史快照，不冒充本次可信位置。重啟不採用快照恢復自動運動。

Wi-Fi／NTP 配置在獨立 NVS blob，只能本地 UART 設定，不包含於一般狀態／設定匯出；BLE bond 由正式堆疊儲存。這些不是加密 Flash 或硬體防拆保證。
