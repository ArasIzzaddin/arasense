import ee
import numpy as np
import torch
from torch_geometric.data import Data

from common.gee import initialize_earth_engine

class ArasenseGraphBuilder:
    """
    Builds a hydrological graph from Digital Elevation Models (DEM).
    Nodes are grid cells, and Edges represent water flow paths.
    """
    
    def __init__(self, project_id):
        try:
            initialize_earth_engine(project_id)
        except Exception as e:
            print(f"Error: {e}")

    def build_hydrological_graph(self, region, scale=1000):
        """
        Extracts DEM data and builds a graph based on flow direction.
        
        Args:
            region (ee.Geometry): The area to model.
            scale (int): Resolution in meters.
        """
        print(f"Building hydrological graph for region at {scale}m scale...")
        
        # 1. Fetch Elevation Data (SRTM)
        dem = ee.Image("USGS/SRTMGL1_003").clip(region).unmask(0)
        
        # 2. Calculate Slope
        slope_img = ee.Terrain.slope(dem).unmask(0)
        
        # 3. Reproject to scale and sample
        full_img = dem.addBands(slope_img).rename(['elevation', 'slope']).reproject(crs='EPSG:4326', scale=scale)
        pixel_data = full_img.sampleRectangle(region)
        
        elevation = np.array(pixel_data.get('elevation').getInfo())
        slope = np.array(pixel_data.get('slope').getInfo())
        
        rows, cols = elevation.shape
        num_nodes = rows * cols
        
        # 4. Create Node Features (Elevation, Slope)
        # Normalize features
        x = torch.tensor(np.stack([
            elevation.flatten() / 3000.0, 
            slope.flatten() / 90.0
        ], axis=1), dtype=torch.float)
        
        # 5. Create Edges (Hydrological Connectivity)
        # For simplicity in this prototype, we connect each pixel to its 
        # neighbors that have a LOWER elevation (downward flow).
        edge_index = []
        
        for r in range(rows):
            for c in range(cols):
                curr_idx = r * cols + c
                curr_elev = elevation[r, c]
                
                # Check 8 neighbors (D8 Flow)
                for dr in [-1, 0, 1]:
                    for dc in [-1, 0, 1]:
                        if dr == 0 and dc == 0: continue
                        
                        nr, nc = r + dr, c + dc
                        if 0 <= nr < rows and 0 <= nc < cols:
                            neigh_idx = nr * cols + nc
                            neigh_elev = elevation[nr, nc]
                            
                            # Edge exists if water can flow from current to neighbor
                            if neigh_elev < curr_elev:
                                edge_index.append([curr_idx, neigh_idx])
        
        edge_index = torch.tensor(edge_index, dtype=torch.long).t().contiguous()
        
        # 6. Construct PyTorch Geometric Data Object
        graph_data = Data(x=x, edge_index=edge_index)
        
        print(f"Graph created with {num_nodes} nodes and {edge_index.shape[1]} edges.")
        return graph_data, (rows, cols)

if __name__ == "__main__":
    PROJECT_ID = 'valid-shine-488311-d6'
    builder = ArasenseGraphBuilder(PROJECT_ID)
    
    # Area in Emilia-Romagna
    emilia_romagna = ee.Geometry.Rectangle([11.0, 44.2, 12.0, 44.8])
    
    graph, shape = builder.build_hydrological_graph(emilia_romagna, scale=2000)
    print(f"Node feature shape: {graph.x.shape}")
    print(f"Edge index shape: {graph.edge_index.shape}")
