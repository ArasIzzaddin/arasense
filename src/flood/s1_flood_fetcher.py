import ee
import numpy as np

class ArasenseFloodFetcher:
    """
    Fetches Sentinel-1 SAR flood masks from Earth Engine.
    Used for training the GNN surrogate.
    """
    
    def __init__(self, project_id):
        try:
            ee.Initialize(project=project_id)
        except Exception as e:
            print(f"Error: {e}")

    def get_flood_mask(self, region, start_date, end_date, scale=1000):
        """
        Generates a flood mask using Sentinel-1 SAR change detection.
        """
        print(f"Generating Sentinel-1 flood mask for {start_date} to {end_date}...")
        
        # 1. Load S1 Collection
        s1 = ee.ImageCollection('COPERNICUS/S1_GRD') \
            .filterBounds(region) \
            .filter(ee.Filter.eq('instrumentMode', 'IW'))
        
        # 2. Filter for flood dates
        flood_col = s1.filterDate(start_date, end_date)
        
        # Check if collection is empty
        count = flood_col.size().getInfo()
        if count == 0:
            print(f"No Sentinel-1 images found for {start_date} to {end_date}. Returning zero mask.")
            # Return a zero mask based on the region size (approximated)
            return np.zeros((33, 40)) # Placeholder for the grid size
            
        post_flood = flood_col.median().select(['VV', 'VH']).select('VV')
        
        # 3. Simple thresholding for water detection
        # Smooth water surfaces reflect radar away, appearing very dark (< -18dB)
        flood_mask = post_flood.lt(-18).rename('flood_mask')
        
        # 4. Sample the mask at the same grid/scale as our graph
        # Reproject to match the graph builder's resolution
        sampled_mask = flood_mask.reproject(crs='EPSG:4326', scale=scale).unmask(0)
        
        # 5. Extract to numpy
        pixel_data = sampled_mask.sampleRectangle(region)
        mask_array = np.array(pixel_data.get('flood_mask').getInfo())
        
        return mask_array

if __name__ == "__main__":
    PROJECT_ID = 'valid-shine-488311-d6'
    fetcher = ArasenseFloodFetcher(PROJECT_ID)
    
    # Emilia-Romagna May 2023
    er_roi = ee.Geometry.Rectangle([11.0, 44.2, 12.0, 44.8])
    mask = fetcher.get_flood_mask(er_roi, '2023-05-15', '2023-05-25', scale=2000)
    
    print(f"Flood mask shape: {mask.shape}")
    print(f"Total flooded nodes: {np.sum(mask)}")
