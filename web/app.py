"""
Web Application Runner
Run Flask development server for Sorting System Dashboard
"""

import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web import create_app

app = create_app()

if __name__ == '__main__':
    # Configuration from settings
    from config.settings import WEB_HOST, WEB_PORT, WEB_DEBUG
    
    print("\n" + "=" * 60)
    print("  SORTING SYSTEM WEB DASHBOARD")
    print("=" * 60)
    print(f"  Server: http://{WEB_HOST}:{WEB_PORT}")
    print(f"  Debug Mode: {WEB_DEBUG}")
    print("=" * 60 + "\n")
    
    app.run(
        host=WEB_HOST,
        port=WEB_PORT,
        debug=WEB_DEBUG,
        threaded=True
    )
