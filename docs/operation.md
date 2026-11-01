# 序列與 BLE 維修操作

平常只需要網頁，見 [web.md](web.md)。這份是沒有網頁可用時的維修方式。

## UART 指令

115200 baud，每行一個指令（接線見 [wiring.md](wiring.md) 的序列救援）：

| 指令 | 作用 |
|---|---|
| `status` | 三段 JSON 狀態 |
| `access` | 印出熱點名稱、密碼與區網網址 |
| `pause` | 暫停，目前這段移動走完才停 |
| `stop` | 立刻關閉線圈，位置失效 |
| `pair` | 開啟 120 秒 BLE 配對，印出六位數 passkey |
| `wifi {"ssid":"…","password":"…"}` | 設定 Wi-Fi（不驗證連線，網頁版才會驗證） |
| `ntp {"servers":["pool.ntp.org"]}` | 改 NTP 伺服器 |
| `clear_bonds CONFIRM` | 清除 BLE 配對 |
| `reset_config CONFIRM` | 清除已存的設定與位置 |

除了 `status`、`access`、`pause`、`stop`，其他要先暫停並等動作結束。也可直接貼 JSON 指令。

## BLE

第一次先在 UART 輸入 `pair`，120 秒內依系統提示輸入 passkey。桌面工具：

```powershell
python tools/ble_client.py --scan
python tools/ble_client.py --address <掃描到的位址>
```

互動模式可下 `status`、`time`、`display 10:30`、`pages 1`、`preview`、`resume`、`pause`、`stop`、`save`。尚未在真實手機上驗收配對。

## 故障

| 訊息 | 意思 | 處理 |
|---|---|---|
| `E_MOTOR_TIMEOUT` | 移動超過時限，線圈已關 | 按「清除故障」，重新歸零 |
| `E_NVS` | 設定寫入失敗 | 再試一次；反覆失敗可用 `reset_config CONFIRM`，要重新歸零 |
| `E_TIME_JUMP` | 時間突然跳動，已暫停 | 確認時間正確後按「儲存並開始走時」 |
