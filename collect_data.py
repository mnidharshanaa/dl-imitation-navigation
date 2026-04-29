import pandas as pd
import os
import pygame
from simulator import run_simulation, CAR_WIDTH, CAR_HEIGHT, MAX_SENSOR_DIST

# Settings
DATA_FILE = "driving_data.csv"
LOG_INTERVAL = 3  # Log every 3 frames (~20Hz at 60FPS)
BUFFER_SIZE = 120 # Keep last 120 logged frames for "Undo" (approx 6 seconds)

class DataCollector:
    def __init__(self):
        self.data_buffer = []
        self.is_recording = False
        self.frame_count = 0
        self.total_samples = 0
        
        # Load existing data if it exists
        if os.path.exists(DATA_FILE):
            self.total_samples = len(pd.read_csv(DATA_FILE))
        else:
            # Create file with headers
            df = pd.DataFrame(columns=['left', 'front', 'right', 'action'])
            df.to_csv(DATA_FILE, index=False)

    def log_frame(self, car, action):
        if not self.is_recording:
            return

        # Skip recording if car is in collision or stopped (optional - user can decide)
        if car.collision:
            return

        self.frame_count += 1
        if self.frame_count % LOG_INTERVAL == 0:
            sample = {
                'left': car.sensors[0],
                'front': car.sensors[1],
                'right': car.sensors[2],
                'action': action
            }
            self.data_buffer.append(sample)
            if len(self.data_buffer) > BUFFER_SIZE:
                self.save_buffer() # Keep buffer slim or just store everything
    
    def save_buffer(self, clear=True):
        if not self.data_buffer:
            return
        
        df = pd.DataFrame(self.data_buffer)
        df.to_csv(DATA_FILE, mode='a', header=False, index=False)
        self.total_samples += len(self.data_buffer)
        if clear:
            self.data_buffer = []

    def undo_last(self):
        """Discards the current unsaved buffer."""
        count = len(self.data_buffer)
        self.data_buffer = []
        print(f"Discarded last {count} samples.")

collector = DataCollector()

def on_frame(event, car, action, type):
    if type == "EVENT" and event:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_r: # Toggle recording
                collector.is_recording = not collector.is_recording
                if not collector.is_recording:
                    collector.save_buffer()
                print(f"Recording: {collector.is_recording}")
            
            if event.key == pygame.K_z: # Undo buffer
                collector.undo_last()
            
            if event.key == pygame.K_s: # Force save
                collector.save_buffer()
                print("Data saved.")

    if type == "TICK":
        collector.log_frame(car, action)
        return {"recording": collector.is_recording}
    
    return None

def main():
    print("--- DATA COLLECTION MODE ---")
    print("Controls:")
    print("  WASD: Drive")
    print("  R: Toggle Recording")
    print("  Z: Undo (Discard unsaved buffer)")
    print("  S: Save current buffer")
    print(f"Initial samples in {DATA_FILE}: {collector.total_samples}")
    
    # We'll need a way to show the recording status in the simulator.
    # I'll modify run_simulation to accept a custom draw callback too.
    
    run_simulation(on_frame=on_frame)
    
    # Final save
    collector.save_buffer()
    print(f"Collection finished. Total samples: {collector.total_samples}")

if __name__ == "__main__":
    main()
