import ee
import os

def initialize_gee():
    """Initializes Google Earth Engine."""
    try:
        ee.Initialize()
        print("Earth Engine initialized successfully.")
    except Exception as e:
        print("Earth Engine failed to initialize. You may need to run 'earthengine authenticate'.")
        print(f"Error: {e}")

def check_dependencies():
    """Checks if key dependencies are installed."""
    libraries = [
        'ee', 'geemap', 'torch', 'torch_geometric', 
        'streamlit', 'pandas', 'plotly', 'sklearn'
    ]
    missing = []
    for lib in libraries:
        try:
            __import__(lib.replace('-', '_'))
        except ImportError:
            missing.append(lib)
    
    if missing:
        print(f"Missing libraries: {', '.join(missing)}")
    else:
        print("All key dependencies are installed.")

if __name__ == "__main__":
    print("--- Aras-GreenAnt Platform Setup ---")
    check_dependencies()
    initialize_gee()
