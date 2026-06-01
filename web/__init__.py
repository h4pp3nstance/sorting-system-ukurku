"""
Web Module
Flask-based web interface for Sorting System Dashboard
Using IBM Carbon Design System for UI
"""

import os
import secrets

from flask import Flask

def create_app():
    """Application factory"""
    app = Flask(__name__)

    app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY') or secrets.token_hex(32)
    
    # Register blueprints
    from .routes import main_bp, api_bp
    from .auth import auth_bp
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(auth_bp)

    from .auth import current_user

    @app.context_processor
    def inject_user():
        user = current_user()
        unread = 0
        if user and user.get('role') == 'mitra':
            from web import mpc_store
            unread = mpc_store.unread_count(to_mitra_id=user.get('mitra_id'))
        return {'user': user, 'unread_notifications': unread}

    return app
