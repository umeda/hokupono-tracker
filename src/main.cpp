#include <Arduino.h>
#include <Servo.h>

// Servo objects
Servo azServo;
Servo elServo;

// Pin Definitions
const int AZ_PIN = 9;
const int EL_PIN = 10;

// LED Pin Definitions
// LED1: R-Pin 3, G-Pin 5, B-Pin 6 (All PWM)
const int LED1_R_PIN = 3; // PWM pin
const int LED1_G_PIN = 5; // PWM pin
const int LED1_B_PIN = 6; // PWM pin


// Serial Parsing
String inputBuffer = "";

void setup() {
    // Attach servos to their respective pins
    azServo.attach(AZ_PIN);
    elServo.attach(EL_PIN);

    // Prevent heap fragmentation by reserving space for the command buffer
    inputBuffer.reserve(25);

    // Initialize LED pins as outputs
    // For PWM pins (3, 5, 6), analogWrite will set them as OUTPUT automatically.
    pinMode(LED1_R_PIN, OUTPUT);
    pinMode(LED1_G_PIN, OUTPUT);
    pinMode(LED1_B_PIN, OUTPUT);

    // Initialize serial communication at 115200 baud
    Serial.begin(115200);
    
    // Initial position: North at 0 elevation, and turn off LEDs
    azServo.write(180); // Initial position adjusted for reversed mounting
    elServo.write(180); // Adjusted for reversed mounting

    // Turn off both LEDs initially (Black)
    analogWrite(LED1_R_PIN, 0);
    analogWrite(LED1_G_PIN, 0);
    analogWrite(LED1_B_PIN, 0);
}

// Helper to convert a single hex digit to 8-bit PWM value
int hexToPWM(char c) {
    if (c >= '0' && c <= '9') return (c - '0') * 17;
    if (c >= 'a' && c <= 'f') return (c - 'a' + 10) * 17;
    if (c >= 'A' && c <= 'F') return (c - 'A' + 10) * 17;
    return 0;
}

/**
 * Transforms 0-359 Azimuth and 0-90 Elevation into servo-safe angles.
 * Handles the reciprocal flip if Azimuth exceeds 179 degrees.
 */
void updateServoPositions(int az, int el) {
    int finalAz;
    int finalEl;

    if (az <= 179) {
        // Normal range
        finalAz = 180 - az; // Reversed for upside-down mount
        finalEl = 180 - el; // Reversed for inverted mount
    } else {
        // Reciprocal range: 180-359
        // Point azimuth to opposite side and flip elevation over the top
        finalAz = 180 - (az - 180); // Reversed for upside-down mount
        finalEl = el; // Double inversion (180 - (180 - el)) simplifies to el
    }

    // Constraint checks to prevent servo strain
    finalAz = constrain(finalAz, 0, 180);
    finalEl = constrain(finalEl, 0, 180);

    azServo.write(finalAz);
    elServo.write(finalEl);
}

void processCommand(String cmd) {
    // Expected format: azelXXX,YY
    if (cmd.startsWith("azel") && cmd.length() >= 10) {
        int commaIndex = cmd.indexOf(',');
        if (commaIndex != -1) {
            int az = cmd.substring(4, commaIndex).toInt();
            int el = cmd.substring(commaIndex + 1).toInt();
            
            updateServoPositions(az, el);
            Serial.print(" ACK\n");
        }
    } else if (cmd.startsWith("colr") && cmd.length() >= 7) {
        // Format: colrRGB (where R, G, B are single hex digits)
        analogWrite(LED1_R_PIN, hexToPWM(cmd.charAt(4)));
        analogWrite(LED1_G_PIN, hexToPWM(cmd.charAt(5)));
        analogWrite(LED1_B_PIN, hexToPWM(cmd.charAt(6)));
        Serial.print(" ACK\n");
    }
}

void loop() {
    while (Serial.available() > 0) {
        char c = Serial.read();
        
        if (c == '\n' || c == '\r') {
            if (inputBuffer.length() > 0) {
                processCommand(inputBuffer);
                inputBuffer = ""; // Clear buffer for next command
            }
        } else {
            inputBuffer += c;
        }

        // Safety: Prevent buffer overflow if malformed data arrives
        if (inputBuffer.length() > 20) {
            inputBuffer = "";
        }
    }
}
