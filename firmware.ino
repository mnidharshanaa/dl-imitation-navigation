// FINAL AI FIRMWARE v4.0 (Non-Blocking Soft-Start)
#define ENA 5
#define IN1 8
#define IN2 9
#define IN3 10
#define IN4 11
#define ENB 6

int trigPins[] = {2, 4, 12}; // Front, Left, Right
int echoPins[] = {3, 7, 13};

int currentSpeedA = 0;
int currentSpeedB = 0;
int targetSpeedA = 0;
int targetSpeedB = 0;

unsigned long lastRampTime = 0;

void setup() {
  Serial.begin(115200);
  pinMode(ENA, OUTPUT); pinMode(IN1, OUTPUT); pinMode(IN2, OUTPUT);
  pinMode(IN3, OUTPUT); pinMode(IN4, OUTPUT); pinMode(ENB, OUTPUT);
  for(int i=0; i<3; i++) { pinMode(trigPins[i], OUTPUT); pinMode(echoPins[i], INPUT); }
}

long getDistance(int i) {
  digitalWrite(trigPins[i], LOW); delayMicroseconds(2);
  digitalWrite(trigPins[i], HIGH); delayMicroseconds(10);
  digitalWrite(trigPins[i], LOW);
  long d = pulseIn(echoPins[i], HIGH, 12000); // 12ms timeout is enough for 2 meters
  return (d == 0) ? 300 : d * 0.034 / 2;
}

void loop() {
  // 1. Report Sensors (Instant)
  Serial.print(getDistance(1));    Serial.print(","); 
  Serial.print(getDistance(0));    Serial.print(","); 
  Serial.println(getDistance(2));                     

  // 2. Listen for Action (Instant)
  if (Serial.available() > 0) {
    int action = Serial.read() - '0';
    updateAction(action);
  }

  // 3. Perform Ramping (Non-Blocking)
  if (millis() - lastRampTime > 4) { 
    if (targetSpeedA == 0) currentSpeedA = 0; 
    else if (currentSpeedA < targetSpeedA) currentSpeedA += 25;
    else if (currentSpeedA > targetSpeedA) currentSpeedA -= 25;
    
    if (targetSpeedB == 0) currentSpeedB = 0; 
    else if (currentSpeedB < targetSpeedB) currentSpeedB += 25;
    else if (currentSpeedB > targetSpeedB) currentSpeedB -= 25;

    currentSpeedA = constrain(currentSpeedA, 0, 255);
    currentSpeedB = constrain(currentSpeedB, 0, 255);

    analogWrite(ENA, currentSpeedA);
    analogWrite(ENB, currentSpeedB);
    lastRampTime = millis();
  }
  delay(10); // Small stability delay
}

void updateAction(int action) {
  int drive_speed = 220; // Increased for better floor movement
  int turn_speed = 255;  // Max torque for pivoting
  
  switch(action) {
    case 1: targetSpeedA = drive_speed; targetSpeedB = drive_speed; digitalWrite(IN1, 1); digitalWrite(IN2, 0); digitalWrite(IN3, 1); digitalWrite(IN4, 0); break;
    case 2: targetSpeedA = turn_speed;  targetSpeedB = turn_speed;  digitalWrite(IN1, 0); digitalWrite(IN2, 1); digitalWrite(IN3, 1); digitalWrite(IN4, 0); break;
    case 3: targetSpeedA = turn_speed;  targetSpeedB = turn_speed;  digitalWrite(IN1, 1); digitalWrite(IN2, 0); digitalWrite(IN3, 0); digitalWrite(IN4, 1); break;
    case 4: targetSpeedA = drive_speed/2; targetSpeedB = drive_speed; digitalWrite(IN1, 1); digitalWrite(IN2, 0); digitalWrite(IN3, 1); digitalWrite(IN4, 0); break;
    case 5: targetSpeedA = drive_speed; targetSpeedB = drive_speed/2; digitalWrite(IN1, 1); digitalWrite(IN2, 0); digitalWrite(IN3, 1); digitalWrite(IN4, 0); break;
    case 6: targetSpeedA = drive_speed; targetSpeedB = drive_speed; digitalWrite(IN1, 0); digitalWrite(IN2, 1); digitalWrite(IN3, 0); digitalWrite(IN4, 1); break;
    default: targetSpeedA = 0; targetSpeedB = 0; currentSpeedA = 0; currentSpeedB = 0; break; // Instant Stop
  }
}
