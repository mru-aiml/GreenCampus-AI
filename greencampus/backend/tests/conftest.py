"""pytest configuration – ensure backend directory is on sys.path."""
import sys
import os

# Add backend to path so imports in tests work without package setup
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
