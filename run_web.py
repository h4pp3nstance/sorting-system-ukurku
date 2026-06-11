#!/usr/bin/env python3
"""
Run Web Server
Simple script to run the Flask web dashboard
"""

import os
import sys

# Ensure we're in the right directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load .env file if python-dotenv is available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed, continue without it

def main():
    from web import create_app
    from config.settings import WEB_HOST, WEB_PORT, WEB_DEBUG

    print("\n" + "=" * 60)
    print("  SORTING SYSTEM WEB DASHBOARD")
    print("=" * 60)
    print(f"  URL: http://{WEB_HOST}:{WEB_PORT}")
    print(f"  Debug: {WEB_DEBUG}")
    print("  Press Ctrl+C to stop")
    print("=" * 60 + "\n")
    
    app = create_app()
    app.run(host=WEB_HOST, port=WEB_PORT, debug=WEB_DEBUG, threaded=True)

if __name__ == '__main__':
    main()
