import pandas as pd
import numpy as np
import os

INPUT_FILE = "driving_data.csv"
OUTPUT_FILE = "augmented_driving_data.csv"

def augment():
    if not os.path.exists(INPUT_FILE):
        print(f"Error: {INPUT_FILE} not found.")
        return

    print(f"Reading {INPUT_FILE}...")
    df = pd.read_csv(INPUT_FILE)
    initial_count = len(df)
    
    # 1. Filter out excessive STOP (action 0) samples
    # Keep STOP only if front sensor is very low (collision/near wall) or randomly keep 5%
    mask_stop = df['action'] == 0
    df_stop = df[mask_stop]
    df_moving = df[~mask_stop]
    
    # Keep 10% of stops to maintain some "stop" behavior without overriding everything
    df_stop_sampled = df_stop.sample(frac=0.1, random_state=42)
    
    # 2. Recombine
    df_filtered = pd.concat([df_moving, df_stop_sampled])
    print(f"Filtered out {initial_count - len(df_filtered)} excessive STOP samples.")

    # 3. Horizontal Flip Augmentation
    # Actions: 2: LEFT, 3: RIGHT, 4: FORWARD_LEFT, 5: FORWARD_RIGHT
    # Sensor mapping: left <-> right
    
    df_flip = df_filtered.copy()
    
    # Swap sensors
    temp_left = df_flip['left'].copy()
    df_flip['left'] = df_flip['right']
    df_flip['right'] = temp_left
    
    # Swap actions
    action_map = {2: 3, 3: 2, 4: 5, 5: 4}
    df_flip['action'] = df_flip['action'].replace(action_map)
    
    # 4. Perfect Balancing (Upsampling)
    # We want Forward, Left, and Right to have roughly equal representation
    counts = df_flip['action'].value_counts()
    # Focus on moving actions: 1, 2, 3 (and 4, 5 if they exist)
    moving_actions = [a for a in [1, 2, 3, 4, 5] if a in counts]
    if moving_actions:
        max_count = counts[moving_actions].max()
        print(f"Targeting {max_count} samples per moving action.")
        
        balanced_chunks = [df_filtered[df_filtered['action'] == 0].sample(frac=0.1)] # Keep some stops
        
        for action in moving_actions:
            action_df = df_flip[df_flip['action'] == action]
            if len(action_df) > 0:
                # Give FORWARD slightly more samples (1.5x) to encourage straight driving
                target = int(max_count * 1.5) if action == 1 else max_count
                upsampled = action_df.sample(n=target, replace=True, random_state=42)
                balanced_chunks.append(upsampled)
        
        df_balanced = pd.concat(balanced_chunks)
    else:
        df_balanced = df_flip

    # 5. Noise Injection on the balanced set
    def add_noise(df_batch, noise_level=0.03): # Increased noise level for robustness
        df_noise = df_batch.copy()
        # Only add noise to sensor columns
        for col in ['left', 'front', 'right']:
            noise = np.random.normal(0, noise_level, size=len(df_noise))
            df_noise[col] = (df_noise[col] + noise).clip(0, 1)
        return df_noise

    # Create variations to make the dataset "huge" as requested
    variations = [df_balanced]
    for _ in range(3): # Create 3 noisy variations
        variations.append(add_noise(df_balanced))
    
    df_final = pd.concat(variations)
    
    # Shuffle
    df_final = df_final.sample(frac=1, random_state=42).reset_index(drop=True)
    
    print(f"Final augmented dataset size: {len(df_final)} samples.")
    print("New action distribution:")
    print(df_final['action'].value_counts().to_dict())
    
    df_final.to_csv(OUTPUT_FILE, index=False)
    print(f"Saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    augment()
