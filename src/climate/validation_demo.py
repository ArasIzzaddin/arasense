import ee
import os
from data_fetcher import ArasenseDataFetcher
from aras_eval import ArasDiagram

def run_validation():
    PROJECT_ID = 'valid-shine-488311-d6'
    fetcher = ArasenseDataFetcher(PROJECT_ID)
    
    # 1. Define ROI (Rome area)
    roi = ee.Geometry.Point([12.4964, 41.9028]).buffer(100000) # 100km radius
    
    # 2. Fetch Data (Temperature for 2014)
    print("Step 1: Fetching real data from GEE...")
    data = fetcher.get_climate_data(roi, '2014-01-01', '2014-12-31', 'temperature')
    
    # 3. Apply Aras Diagram
    print("\nStep 2: Calculating Aras Metrics...")
    aras = ArasDiagram(
        reference_data=data['reference'], 
        model_data=[data['model']], 
        model_names=["ACCESS-CM2 (Historical)"]
    )
    
    # 4. Print Results
    results = aras.results[0]
    print("\n--- Arasense Evaluation Results ---")
    print(f"Model: {results['name']}")
    print(f"Bias (α): {results['alpha']:.2f}%")
    print(f"Variability (β): {results['beta']:.2f}%")
    print(f"Correlation: {results['correlation']:.2f}")
    print(f"Total Percentage Error (E): {results['e_total']:.2f}%")
    print("-----------------------------------")
    
    # 5. Export/Save Plot (Optional for CLI)
    # fig = aras.plot()
    # fig.write_image("aras_diagram_italy.png")

if __name__ == "__main__":
    run_validation()
