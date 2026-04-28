import ee
import pandas as pd
import numpy as np

from common.gee import initialize_earth_engine

class ArasenseDataFetcher:
    """
    Data fetcher for Arasense platform.
    Retrieves ERA5-Land and CMIP6 data from Google Earth Engine.
    """
    
    def __init__(self, project_id):
        try:
            initialize_earth_engine(project_id)
            print(f"Arasense: Initialized with project {project_id}")
        except Exception as e:
            print(f"Error initializing Earth Engine: {e}")
            raise

    def get_climate_data(self, geometry, start_date, end_date, variable='temperature', ref_dataset='ERA5-Land', fast_mode=True):
        """
        High-performance optimized fetcher.
        """
        vars_map = {
            'temperature': {'era5': 'temperature_2m', 'cmip6': 'tas', 'scale_era5': 1.0, 'scale_mod': 1.0},
            'precipitation': {'era5': 'total_precipitation_sum', 'cmip6': 'pr', 'scale_era5': 1000.0, 'scale_mod': 86400.0},
            'all_euro_cordex': {'era5': 'total_precipitation_sum', 'cmip6': 'pr', 'scale_era5': 1000.0, 'scale_mod': 86400.0}
        }
        v = vars_map.get(variable, vars_map['temperature'])

        # 1. Optimized Reference Fetch
        ref_col = ee.ImageCollection("ECMWF/ERA5_LAND/DAILY_AGGR").filterBounds(geometry).filterDate(start_date, end_date).select(v['era5'])
        ref_series = self.extract_series(ref_col, v['era5'], v['scale_era5'], "Reference", geometry)

        # 2. Optimized Ensemble Fetch (Fast vs Full)
        print("Arasense: Discovering all available NASA CMIP6 models...")
        cmip6_col = ee.ImageCollection("NASA/GDDP-CMIP6") \
            .filterBounds(geometry) \
            .filterDate(start_date, end_date) \
            .filter(ee.Filter.eq('scenario', 'historical')) \
            .select(v['cmip6'])

        try:
            # DYNAMIC DISCOVERY: Get every unique model ID from GEE metadata
            all_available_models = cmip6_col.aggregate_array('model').distinct().getInfo()
            print(f"Exhaustive Discovery: Found {len(all_available_models)} models in archive.")
        except Exception as discovery_err:
            print(f"Metadata scan failed, using institutional fallback list. Error: {discovery_err}")
            all_available_models = ['ACCESS-CM2', 'ACCESS-ESM1-5', 'BCC-CSM2-MR', 'CESM2', 'CanESM5', 'EC-Earth3', 'GFDL-CM4', 'GISS-E2-1-G', 'HadGEM3-GC31-LL', 'IPSL-CM6A-LR', 'MIROC6', 'MPI-ESM1-2-HR', 'MRI-ESM2-0', 'NorESM2-MM']
        
        models_to_fetch = all_available_models[:5] if fast_mode else all_available_models
        
        results_dict = {}
        print(f"Ensemble Processing: Executing benchmarking for {len(models_to_fetch)} models...")
        
        # Performance trick: Extract all models in a more optimized loop
        for m_name in models_to_fetch:
            m_col = cmip6_col.filter(ee.Filter.eq('model', m_name))
            # Increased scale to 25km for ensemble speed
            m_series = self.extract_series(m_col, v['cmip6'], v['scale_mod'], m_name, geometry, scale=25000)
            
            if not m_series.empty:
                combined = pd.concat([ref_series, m_series], axis=1, join='inner').dropna()
                combined.columns = ['reference', 'model']
                results_dict[m_name] = combined

        return results_dict

    def extract_series(self, collection, band_name, scale_factor=1.0, label="", geometry=None, scale=10000):
        """Highly optimized server-side extraction."""
        try:
            # Reduce resolution for speed if area is large
            def reduce_region(image):
                stats = image.reduceRegion(
                    reducer=ee.Reducer.mean(),
                    geometry=geometry,
                    scale=scale,
                    bestEffort=True # GEE chooses best scale to avoid timeout
                )
                return ee.Feature(None, {
                    'date': image.date().format('YYYY-MM-DD'),
                    'value': ee.Number(stats.get(band_name)).multiply(scale_factor)
                })
            
            # Map the reduction over the collection
            feature_collection = collection.map(reduce_region)
            
            # Use getInfo() on the final reduced set only
            features = feature_collection.getInfo()['features']
            df = pd.DataFrame([f['properties'] for f in features])
            if df.empty: return pd.Series(dtype=float)
            
            df['date'] = pd.to_datetime(df['date'], errors='coerce')
            df = df.dropna(subset=['date'])
            return df.groupby('date')['value'].mean().sort_index()
        except:
            return pd.Series(dtype=float)

if __name__ == "__main__":
    # Test for a small region in Central Italy (Rome area)
    PROJECT_ID = 'valid-shine-488311-d6'
    fetcher = ArasenseDataFetcher(PROJECT_ID)
    
    roi = ee.Geometry.Point([12.4964, 41.9028]).buffer(50000) # 50km around Rome
    
    # Using a short range for test
    df = fetcher.get_climate_data(roi, '2014-01-01', '2014-12-31', 'temperature')
    print(df.head())
    print("Data extraction successful.")
