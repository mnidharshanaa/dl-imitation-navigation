import torch
import torch.nn as nn
import serial
import time
import os
import statistics
from collections import deque

# --- SETTINGS ---
MODEL_FILE = "model.pth"
PORT = "COM3"
BAUD = 115200

class DrivingModel(nn.Module):
    def __init__(self):
        super(DrivingModel, self).__init__()
        self.fc = nn.Sequential(
            nn.Linear(3, 128), # Must match train_model.py
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(128, 128),
            nn.ReLU(),
            nn.Linear(128, 6)
        )
    def forward(self, x):
        return self.fc(x)

class HardwareDriver:
    def __init__(self):
        self.device = torch.device("cpu")
        self.model = DrivingModel().to(self.device)
        if os.path.exists(MODEL_FILE):
            self.model.load_state_dict(torch.load(MODEL_FILE, map_location=self.device))
            self.model.eval()
            print("AI Model Loaded Successfully.")
        else:
            print(f"Error: {MODEL_FILE} not found.")

        try:
            self.ser = serial.Serial(PORT, BAUD, timeout=1.0)
            self.ser.flushInput()
            time.sleep(2)
            print(f"Connected to Arduino on {PORT}")
        except Exception as e:
            print(f"Serial Connection Error: {e}")
            self.ser = None

        # --- ACTION PERSISTENCE (Solves oscillation/spinning) ---
        self.last_sent_action = -1
        self.committed_action = None   # Turn we are locked into
        self.commit_until     = 0.0    # Time when lock expires
        self.COMMIT_DURATION  = 0.8    # Seconds to hold a turn
        self.EMERGENCY_CM     = 10.0   # cm: always override lock

        # Heartbeat: re-send current action every N seconds
        self.last_sent_time   = 0.0
        self.HEARTBEAT_SEC    = 2.0    # Re-send even if action unchanged

        # Sensor smoothing
        self.sensor_history = deque(maxlen=3)

    def normalize(self, raw_values):
        return [min(v / 300.0, 1.0) for v in raw_values]

    def run(self):
        if not self.ser:
            return
        print("Starting Hardware Integration... Press Ctrl+C to stop.")

        try:
            while True:
                # 1. Read from Arduino
                line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                if not line:
                    continue

                try:
                    raw_sensors = [float(x) for x in line.split(',')]
                    if len(raw_sensors) != 3:
                        continue
                except:
                    continue

                # 2. Median filter (remove ultrasonic glitches)
                self.sensor_history.append(raw_sensors)
                smooth = [
                    statistics.median([s[i] for s in self.sensor_history])
                    for i in range(3)
                ]
                sensors = self.normalize(smooth)

                # 3. AI Decision
                input_t = torch.tensor([sensors], dtype=torch.float32).to(self.device)
                with torch.no_grad():
                    out = self.model(input_t)
                    _, pred = torch.max(out, 1)
                    ai_action = pred.item() + 1  # Convert 0-5 → 1-6

                # 4. ACTION PERSISTENCE — Maneuver Commitment
                now = time.time()
                closest_cm = min(raw_sensors)
                all_clear = all(s > 150.0 for s in raw_sensors)

                if closest_cm < self.EMERGENCY_CM:
                    # EMERGENCY: Something touching → override lock instantly
                    final_action = ai_action
                    self.commit_until = 0  # Cancel lock
                elif all_clear:
                    # ALL CLEAR: Path completely open → release lock, go forward
                    self.commit_until = 0
                    final_action = 1  # Forward
                elif now < self.commit_until:
                    # LOCK ACTIVE: Finish the committed turn
                    final_action = self.committed_action
                else:
                    # FREE: Use AI decision
                    final_action = ai_action
                    # If AI chose a turn → commit to it
                    if ai_action in [2, 3, 4, 5]:
                        self.committed_action = ai_action
                        self.commit_until = now + self.COMMIT_DURATION

                # 5. Send to Arduino: on action change OR every 2s heartbeat
                action_changed = (final_action != self.last_sent_action)
                heartbeat_due  = (now - self.last_sent_time) >= self.HEARTBEAT_SEC

                if action_changed or heartbeat_due:
                    self.ser.write(str(final_action).encode())
                    self.last_sent_action = final_action
                    self.last_sent_time   = now

                status = "LOCKED" if now < self.commit_until else "FREE  "
                print(f"Sensors: {raw_sensors} | AI: {ai_action} | Out: {final_action} | {status}")

        except KeyboardInterrupt:
            print("Stopping...")
            try:
                self.ser.write(b"0")
            except Exception:
                pass  # Port may have already closed
            try:
                self.ser.close()
            except Exception:
                pass

if __name__ == "__main__":
    driver = HardwareDriver()
    driver.run()
