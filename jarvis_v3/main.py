"""
JARVIS - Desktop AI Assistant
Main entry point
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ui.app import JarvisApp


def main():
    app = JarvisApp()
    app.run()


if __name__ == "__main__":
    main()
