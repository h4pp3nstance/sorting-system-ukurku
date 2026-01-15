"""
Web Module
Flask-based web interface for Sorting System Dashboard
Using IBM Carbon Design System for UI
"""

from flask import Flask

def create_app():
    """Application factory"""
    app = Flask(__name__)
    
    # Configuration
    app.config['SECRET_KEY'] = 'sorting-system-secret-key-change-in-production'
    
    # Register blueprints
    from .routes import main_bp, api_bp
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp, url_prefix='/api')
    
    return app
