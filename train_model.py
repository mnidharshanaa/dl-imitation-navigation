import pandas as pd
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
from sklearn.model_selection import train_test_split
import os

# Settings
DATA_FILE = "augmented_driving_data.csv"
MODEL_FILE = "model.pth"

class DrivingModel(nn.Module):
    def __init__(self):
        super(DrivingModel, self).__init__()
        self.fc = nn.Sequential(
            nn.Linear(3, 128), 
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(128, 128),
            nn.ReLU(),
            nn.Linear(128, 6)
        )
    def forward(self, x): return self.fc(x)

def generate_synthetic_data(num_samples=5000):
    print(f"Generating {num_samples} synthetic perfect-driving samples...")
    data = []
    for _ in range(num_samples):
        l, f, r = np.random.uniform(2, 300, 3)
        # Priority: Low → High (last match wins is avoided by using if/elif)
        if l < 25 or r < 25 or f < 40:  # Something close
            if f < 15:   action = 6  # Emergency Reverse
            elif l < 25: action = 3  # Wall on Left  → Turn Right
            elif r < 25: action = 2  # Wall on Right → Turn Left
            elif f < 40: action = 3  # Front closing → Turn Right (default)
            else:        action = 1
        else:
            action = 1  # All clear: Go Forward
        data.append([l, f, r, action])
    return pd.DataFrame(data, columns=['left', 'front', 'right', 'action'])

def train():
    df_real = pd.read_csv(DATA_FILE) if os.path.exists(DATA_FILE) else pd.DataFrame()
    df_synth = generate_synthetic_data(5000)
    
    # Blend them together
    df = pd.concat([df_real, df_synth], ignore_index=True)
    print(f"Total Dataset: {len(df)} (Real: {len(df_real)}, Synth: 5000)")

    # 1. NORMALIZE (Internal 0-1)
    df['left'] = np.clip(df['left'] / 300.0, 0.0, 1.0)
    df['front'] = np.clip(df['front'] / 300.0, 0.0, 1.0)
    df['right'] = np.clip(df['right'] / 300.0, 0.0, 1.0)
    
    # --- PRIORITY RULES (applied low→high, so critical rules win) ---
    # Level 1: All clear → Forward (only if ALL sensors show wide open space)
    df.loc[(df['front'] > 0.20) & (df['left'] > 0.17) & (df['right'] > 0.17), 'action'] = 1

    # Level 2: Side wall avoidance — react at 50cm (0.17)
    df.loc[df['right'] < 0.17, 'action'] = 2  # Right wall → Turn Left
    df.loc[df['left']  < 0.17, 'action'] = 3  # Left wall  → Turn Right

    # Level 3: Front obstacle at 60cm → pick the wider side
    df.loc[(df['front'] < 0.20) & (df['left'] > df['right']), 'action'] = 2
    df.loc[(df['front'] < 0.20) & (df['right'] >= df['left']), 'action'] = 3

    # Level 4 (HIGHEST PRIORITY): Emergency Reverse at 30cm
    df.loc[df['front'] < 0.10, 'action'] = 6
    
    y = (df['action'].values - 1).astype(np.int64)
    X = df[['left', 'front', 'right']].values.astype(np.float32)

    # 2. CALCULATE CLASS WEIGHTS (To handle imbalance)
    class_counts = np.bincount(y, minlength=6)
    # Avoid div by zero
    weights = 1.0 / (class_counts + 1)
    weights = weights / weights.sum()
    class_weights = torch.tensor(weights, dtype=torch.float32)
    print(f"Applying Class Weights: {weights}")

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.15)
    train_loader = DataLoader(TensorDataset(torch.tensor(X_train), torch.tensor(y_train)), batch_size=64, shuffle=True)

    model = DrivingModel()
    # Apply the weights to the Loss function!
    criterion = nn.CrossEntropyLoss(weight=class_weights)
    optimizer = optim.Adam(model.parameters(), lr=0.001)

    print("Training High-Accuracy Model (200 Epochs)...")
    for epoch in range(200):
        model.train()
        for inputs, labels in train_loader:
            optimizer.zero_grad()
            loss = criterion(model(inputs), labels)
            loss.backward()
            optimizer.step()
        if (epoch + 1) % 50 == 0:
            print(f"Epoch {epoch+1} complete.")

    # Evaluation
    model.eval()
    with torch.no_grad():
        X_test_t = torch.tensor(X_test, dtype=torch.float32)
        y_test_t = torch.tensor(y_test, dtype=torch.long)
        outputs = model(X_test_t)
        _, predicted = torch.max(outputs, 1)
        correct = (predicted == y_test_t).sum().item()
        accuracy = correct / y_test_t.size(0)
        print(f"\nTraining Complete!")
        print(f"Test Accuracy: {accuracy * 100:.1f}%")

    # Save model
    torch.save(model.state_dict(), MODEL_FILE)
    print(f"Model saved to {MODEL_FILE}")

if __name__ == "__main__":
    train()
