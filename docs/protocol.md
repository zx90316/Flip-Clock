# 協定與資料格式

完整契約以 [原工程規格第 13–15 節](engineering-spec.zh-TW.md)為準。實作共用 [FlipProtocol.h](../shared/protocol/src/FlipProtocol.h)，不用 C++ 結構記憶體排列傳送。

## I²C v1

ESP 是 100 kHz 唯一主端，Uno 0x12；write/read 都恰好 32 bytes，讀狀態不先寫暫存器索引。多位元整數 little-endian。

| 位移 | 長度 | 欄位 |
|---|---|---|
| 0 | 1 | 0xA5 |
| 1 | 1 | version=1 |
| 2 | 1 | opcode；狀態回覆則 state |
| 3 | 1 | 命令 flags=0；狀態 flags 見下 |
| 4 | 4 | session_id |
| 8 | 4 | command seq；狀態則 job seq |
| 12、16、20、24 | 各 4 | arg0、arg1、arg2、arg3 |
| 28 | 2 | aux |
| 30 | 2 | CRC-16/CCITT-FALSE，LE |

CRC 對 bytes 0–29，poly 0x1021，init 0xFFFF，不反射、不 xorout；`123456789`→0x29B1。獨立 Python 產生的 [vectors.json](../shared/protocol/vectors.json)與 C++ 固定測試向量核對。

命令：OPEN=0x01、ARM=0x02、HEARTBEAT=0x03、MOVE=0x10、STOP=0x11、DISARM=0x12、CLEAR=0x13。未使用欄位為零。MOVE：arg0 有號半步、arg1 速率、arg2 加速度、arg3 timeout ms。正式預設單次 |steps|≤10000、rate≤200、timeout≤120000，反轉拒絕。

狀態：0 BOOT_UNARMED、1 IDLE、2 RUNNING、3 DONE、4 STOPPED、5 FAULT。flags bit0 session_valid、bit1 armed、bit2 position_unknown、bit3 coil_outputs_zero。arg0 已送出的帶方向步數；arg1 尚餘絕對步數；arg2 最近處理的非 heartbeat 命令 seq；arg3 uptime。aux 低 byte 錯誤碼，高 byte 相位 0–7／0xFF。

ACK 不等於受理或完成。ESP 核對 status.arg2 才確認命令已處理，核對 session＋job seq＋DONE＋完整步數＋零剩餘＋無錯誤＋輸出低才提交一頁。heartbeat 不清 DONE／job／進度。

Uno 固定兩槽 RX，ISR 只拷貝資料；主迴圈驗證 CRC、處理命令及運動。STOP 在兩槽中優先處理；佇列滿會鎖 FAULT，不覆蓋原命令。四筆去重 cache 比對完整 30-byte payload；cache 淘汰後以水位拒絕舊 seq。相同 seq 不同內容拒絕。沒有 RAM 記錄就不聲稱可跨掉電去重。

ESP 約 50 ms 輪詢、250 ms 心跳；命令 200 ms 未獲應用層確認，原 frame 最多重送三次。仍不確定或連續無有效狀態時停止排程及心跳，Uno 超過 1500 ms 未獲合法匹配 session heartbeat，關輸出、解除 armed、鎖故障。垃圾包／單純匯流排活動不刷新 lease。

## BLE v1

| 項目 | UUID 尾段（共同格式 b50c10XX-7e6b-4e67-a540-a06c4fe1b201） | 屬性 |
|---|---|---|
| Service | XX=00 | 自訂服務 |
| Command RX | XX=01 | Write with response、加密及驗證 |
| Event TX | XX=02 | Indicate；未訂閱不受理寫入 |
| Info | XX=03 | Read，`1|0.2.0|boot_id`，≤20 bytes |

UTF-8 JSON Lines，以實際 LF 結束；最大每行 512 bytes，最低 MTU 每段 20 bytes。完整 bytes 收齊才解析 JSON；超長行丟棄至 LF，未完成行逾 2 秒丟棄。Indication 等確認後才發下一段，背壓／佇列滿時暫停及斷線，避免遺失結果後繼續排程人工工作。

所有 JSON 命令有 `v:1`、單調 uint32 `id`、正確 `boot_id`、`op`。16 筆 cache 比對完整請求內容及保存結果，相同 id 不同內容 E_ID_REUSE，淘汰舊 id E_STALE_ID。跨 BLE 連線仍保留同一開機的去重表；重啟則換 boot_id，客戶端停止盲目重送。

`get_status` 以三行 part/parts 回同一次查詢快照，單行≤512 bytes；cache 保存整組回覆。設定、即時位置與保存快照分開。`coil_outputs_zero` 只表示 Uno 控制輸出為低，並非電流量測。

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
| 64–75 | 保留 0 |
| 76–79 | CRC32 |

變更先在 RAM，save_config 才保存。未變更的設定及位置不因 RTC 秒數更新而重寫；最短保存節流五秒，定期快照預設 30 分鐘。寫入前解除 armed，寫入後由原 session 再 ARM；寫入期間不動。位置未知時保留先前歷史快照，不冒充本次可信位置。重啟不採用快照恢復自動運動。

Wi-Fi／NTP 配置在獨立 NVS blob，只能本地 UART 設定，不包含於一般狀態／設定匯出；BLE bond 由正式堆疊儲存。這些不是加密 Flash 或硬體防拆保證。
