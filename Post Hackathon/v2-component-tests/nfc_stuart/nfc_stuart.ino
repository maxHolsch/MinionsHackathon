#include <SPI.h>
#include <MFRC522.h>
#include <WiFi.h>
#include <WiFiUdp.h>
#include "driver/i2s.h"

// --- WiFi config ---
#define WIFI_SSID  "Pixel_6992"
#define WIFI_PASS  "erinisangry"

// --- Cloud server ---
#define CLOUD_HOST  "api.mistermatti.com"
#define CLOUD_PORT  9000                       // ESP32 audio TCP port
#define LOG_PORT    12346                      // UDP log port (same host)

// --- RFID pins ---
#define SS_PIN  D3
#define RST_PIN D2

// --- INMP441 I2S pins ---
#define I2S_SCK_PIN  7   // D5 -> GPIO7  (bit clock)
#define I2S_WS_PIN   3   // D1 -> GPIO3  (word select / LRCK)
#define I2S_SD_PIN   2   // D0 -> GPIO2  (serial data, mic output)

// --- Audio config ---
#define SAMPLE_RATE     16000
#define DMA_BUF_COUNT   4
#define DMA_BUF_LEN     512
#define AUDIO_BUF_BYTES (DMA_BUF_LEN * sizeof(int16_t))

// --- Reconnect interval ---
#define RECONNECT_MS 5000

// --- Globals ---
MFRC522    rfid(SS_PIN, RST_PIN);
WiFiClient audioClient;
WiFiUDP    logUdp;

int16_t  audioBuf[DMA_BUF_LEN];
bool     wasConnected      = false;
uint32_t lastConnectAttempt = 0;

// ---------------------------------------------------------------
// Logging — serial + UDP to cloud
// ---------------------------------------------------------------
void sendLog(const char* msg) {
  logUdp.beginPacket(CLOUD_HOST, LOG_PORT);
  logUdp.write((const uint8_t*)msg, strlen(msg));
  logUdp.endPacket();
}

void logf(const char* fmt, ...) {
  char buf[256];
  va_list args;
  va_start(args, fmt);
  vsnprintf(buf, sizeof(buf), fmt, args);
  va_end(args);
  Serial.println(buf);
  sendLog(buf);
}

// ---------------------------------------------------------------
void setup() {
  Serial.begin(115200);

  // SPI + RFID
  SPI.begin(D8, D9, D10, D3);  // SCK, MISO, MOSI, SS
  rfid.PCD_Init();
  delay(4);

  // WiFi
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.print("Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println();

  logUdp.begin(0);  // bind to any local port for TX

  logf("WiFi connected. IP: %s", WiFi.localIP().toString().c_str());
  logf("RSSI: %d dBm", WiFi.RSSI());

  // I2S — INMP441, 16 kHz, 16-bit, mono (L/R tied to GND -> left channel)
  const i2s_config_t i2s_config = {
    .mode                 = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
    .sample_rate          = SAMPLE_RATE,
    .bits_per_sample      = I2S_BITS_PER_SAMPLE_16BIT,
    .channel_format       = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = I2S_COMM_FORMAT_STAND_I2S,
    .intr_alloc_flags     = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count        = DMA_BUF_COUNT,
    .dma_buf_len          = DMA_BUF_LEN,
    .use_apll             = false,
    .tx_desc_auto_clear   = false,
    .fixed_mclk           = 0,
  };
  i2s_driver_install(I2S_NUM_0, &i2s_config, 0, NULL);

  const i2s_pin_config_t pin_config = {
    .bck_io_num    = I2S_SCK_PIN,
    .ws_io_num     = I2S_WS_PIN,
    .data_out_num  = I2S_PIN_NO_CHANGE,
    .data_in_num   = I2S_SD_PIN,
  };
  i2s_set_pin(I2S_NUM_0, &pin_config);
  i2s_zero_dma_buffer(I2S_NUM_0);

  logf("Ready. Connecting to cloud...");
}

// ---------------------------------------------------------------
void loop() {

  // ---- 1. Read I2S audio ----
  size_t bytesRead = 0;
  i2s_read(I2S_NUM_0, audioBuf, AUDIO_BUF_BYTES, &bytesRead, pdMS_TO_TICKS(5));

  if (bytesRead > 0 && audioClient.connected()) {
    audioClient.write((const uint8_t*)audioBuf, bytesRead);
  }

  // ---- 2. Maintain cloud connection (non-blocking reconnect) ----
  bool nowConnected = audioClient.connected();

  if (wasConnected && !nowConnected) {
    logf("Disconnected from cloud. Reconnecting...");
  }

  if (!nowConnected) {
    uint32_t now = millis();
    if (now - lastConnectAttempt >= RECONNECT_MS) {
      lastConnectAttempt = now;
      if (audioClient.connect(CLOUD_HOST, CLOUD_PORT)) {
        logf("Connected to cloud %s:%d", CLOUD_HOST, CLOUD_PORT);
        nowConnected = true;
      }
    }
  }

  wasConnected = nowConnected;

  // ---- 3. RFID (non-blocking) ----
  if (rfid.PICC_IsNewCardPresent() && rfid.PICC_ReadCardSerial()) {
    char uid[32] = "UID:";
    char hex[8];
    for (byte i = 0; i < rfid.uid.size; i++) {
      snprintf(hex, sizeof(hex), " %02X", rfid.uid.uidByte[i]);
      strncat(uid, hex, sizeof(uid) - strlen(uid) - 1);
    }
    logf("%s", uid);
    rfid.PICC_HaltA();
    rfid.PCD_StopCrypto1();
  }
}
