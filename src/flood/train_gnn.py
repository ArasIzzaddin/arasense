import torch
import torch.optim as optim
import torch.nn as nn
from gnn_model import ArasenseFloodGNN
from graph_builder import ArasenseGraphBuilder
from s1_flood_fetcher import ArasenseFloodFetcher
import ee

def train_arasense_gnn():
    PROJECT_ID = 'valid-shine-488311-d6'
    
    # 1. Initialize Engines
    builder = ArasenseGraphBuilder(PROJECT_ID)
    fetcher = ArasenseFloodFetcher(PROJECT_ID)
    
    # 2. Prepare Training Data (Emilia-Romagna Event)
    # Smaller box for faster training demo
    er_roi = ee.Geometry.Rectangle([11.2, 44.3, 11.8, 44.7])
    
    # Build Graph
    graph, shape = builder.build_hydrological_graph(er_roi, scale=2000)
    
    # Fetch Ground Truth (Labels)
    mask = fetcher.get_flood_mask(er_roi, '2023-05-15', '2023-05-25', scale=2000)
    y = torch.tensor(mask.flatten(), dtype=torch.float).view(-1, 1)
    
    # 3. Setup Model, Optimizer, Loss
    model = ArasenseFloodGNN(num_node_features=2) # elevation, slope
    optimizer = optim.Adam(model.parameters(), lr=0.01)
    criterion = nn.BCELoss() # Binary Cross Entropy for flood/no-flood
    
    # 4. Training Loop
    print("\nStarting GNN Training for Arasense...")
    model.train()
    for epoch in range(50):
        optimizer.zero_grad()
        out = model(graph)
        
        # Calculate loss only for the current graph
        loss = criterion(out, y)
        loss.backward()
        optimizer.step()
        
        if (epoch + 1) % 10 == 0:
            print(f"Epoch {epoch+1:02d} | Loss: {loss.item():.4f}")
            
    # 5. Save the trained surrogate
    torch.save(model.state_dict(), "arasense_flood_gnn.pth")
    print("\nTraining Complete. Model saved as 'arasense_flood_gnn.pth'")

if __name__ == "__main__":
    train_arasense_gnn()
