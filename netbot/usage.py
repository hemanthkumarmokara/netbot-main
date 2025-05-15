import sys
import os

# Add the absolute path to the `newtnetbot` folder
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'newtnetbot')))

# Now import directly
from appcopy import lol

# Use the function
print(lol(32, 45))
