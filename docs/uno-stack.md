# Uno 堆疊預算與編譯分析

正式 LTO 韌體靜態 RAM 869 bytes，剩餘 1,179 bytes。下表來自另行 -fno-lto -fstack-usage 分析編譯，不替代正式映像，亦不是實機高水位量測。表中包含 Arduino 核心已編譯但未必鏈結進韌體的函式；出現 String 函式不表示本程式使用動態 String。

| 函式 | 單一 frame bytes | 編譯器分類 |
|---|---:|---|
| `void loop()` | 88 | static |
| `String::String(float, unsigned char)` | 59 | static |
| `String::String(double, unsigned char)` | 59 | static |
| `unsigned char String::concat(float)` | 52 | static |
| `unsigned char String::concat(double)` | 52 | static |
| `void serviceSerial()` | 46 | static |
| `size_t Print::printNumber(long unsigned int, uint8_t)` | 45 | static |
| `void printFrame()` | 41 | static |
| `String::String(long int, unsigned char)` | 40 | static |
| `String::String(long unsigned int, unsigned char)` | 39 | static |
| `void publish()` | 36 | static |
| `flip::Error flip::Endpoint::apply(const flip::Frame&, uint32_t)` | 26 | static |
| `String::String(int, unsigned char)` | 24 | static |
| `void tone(uint8_t, unsigned int, long unsigned int)` | 23 | static |
| `String::String(unsigned int, unsigned char)` | 23 | static |
| `unsigned char String::concat(long int)` | 22 | static |
| `unsigned char String::concat(long unsigned int)` | 21 | static |
| `int Stream::findMulti(Stream::MultiTarget*, int)` | 20 | static |
| `bool Stream::findUntil(char*, size_t, char*, size_t)` | 20 | static |
| `void String::replace(const String&, const String&)` | 20 | static |
| `size_t Print::printFloat(double, uint8_t)` | 19 | static |
| `pulseInLong` | 18 | static |
| `void flip::Endpoint::handle(const flip::Frame&, uint32_t)` | 18 | static |
| `twi_readFrom` | 18 | static |
| `void __vector_19()` | 17 | static |

工程預算：主迴圈及最深呼叫鏈保留 512 bytes，另為 TWI ISR、Wire callback、暫存器與返回位址保留 256 bytes，共 768 bytes；在 1,179-byte 空間中另留 411 bytes 裕量。程式無遞迴或動態配置，receive/request callback 只拷貝固定 32-byte 資料。

這是保守設計預算，未自動證明所有呼叫路徑的全域最壞值；LTO、ISR 巢狀條件與 bootloader 行為仍須實機以 stack canary／高水位量測及壓力測試驗證。不能把單一最大 frame 或剩餘 RAM 當成已驗證最壞堆疊。
