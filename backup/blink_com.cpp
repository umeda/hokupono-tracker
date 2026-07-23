#include <Arduino.h>

unsigned long delay_time = 500; // 500ms ON + 500ms OFF = 1 blink per second
unsigned long last_blink_time = 0;
bool led_state = LOW;

// The onboard LED on a Nano is typically connected to Digital Pin 13
void setup() {
    pinMode(LED_BUILTIN, OUTPUT);
    // Match the monitor_speed in platformio.ini
    Serial.begin(115200);
}

void loop() {
    // Check if a key has been pressed in the terminal
    if (Serial.available() > 0) {
        char command = Serial.read();

        if (command == '+') {
            delay_time = delay_time / 2;
            if (delay_time < 1) delay_time = 1; // Prevent delay from hitting 0
            Serial.println(" ACK");
        } 
        else if (command == '-') {
            delay_time = delay_time * 2;
            Serial.println(" ACK");
        } 
        else if (command == '=') {
            delay_time = 500;
            Serial.println(" ACK");
        }
    }

    // Non-blocking blink logic
    unsigned long current_time = millis();
    if (current_time - last_blink_time >= delay_time) {
        last_blink_time = current_time;
        led_state = !led_state;
        digitalWrite(LED_BUILTIN, led_state);
    }
}
