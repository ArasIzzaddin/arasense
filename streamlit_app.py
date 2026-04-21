import sys
import os

# Add the src directory to the path so imports work correctly
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

# Import the main app logic
from ui.app import *
