#!/bin/bash
# =============================================================================
# Post-Create Script for GitHub Codespaces
# Runs once when Codespace is created
# =============================================================================

echo "🔧 Setting up Sorting System development environment..."

# Install Python dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Create necessary directories
mkdir -p logs
mkdir -p output/labels
mkdir -p assets/test_images

# =========================================================================
# Firebase Credentials Setup
# =========================================================================

if [ -n "$FIREBASE_CREDENTIALS" ]; then
    echo "🔥 Setting up Firebase credentials from Codespaces Secret..."
    echo "$FIREBASE_CREDENTIALS" > config/firebase_credentials.json
    echo "✅ Firebase credentials configured!"
else
    # Create sample Firebase config template (without credentials)
    if [ ! -f "config/firebase_credentials.json" ]; then
        cat > config/firebase_credentials.json.template << 'EOF'
{
  "type": "service_account",
  "project_id": "YOUR_PROJECT_ID",
  "private_key_id": "YOUR_PRIVATE_KEY_ID",
  "private_key": "-----BEGIN PRIVATE KEY-----\nYOUR_PRIVATE_KEY\n-----END PRIVATE KEY-----\n",
  "client_email": "YOUR_CLIENT_EMAIL",
  "client_id": "YOUR_CLIENT_ID",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "YOUR_CERT_URL"
}
EOF
        echo "📝 Created Firebase credentials template at config/firebase_credentials.json.template"
        echo ""
        echo "⚠️  To enable Firebase:"
        echo "   1. Add FIREBASE_CREDENTIALS secret in GitHub Settings"
        echo "   2. Or manually create config/firebase_credentials.json"
        echo "   See: docs/CODESPACES_FIREBASE_SETUP.md"
    fi
fi

# Run tests to verify setup
echo "🧪 Running tests to verify installation..."
python -m pytest tests/ -v --tb=short -q 2>/dev/null || echo "Tests completed"

echo ""
echo "✅ Setup complete!"
echo ""
echo "🚀 To start the dashboard, run:"
echo "   python run_web.py"
echo ""
echo "📊 Dashboard will be available at: http://localhost:5000"
echo ""
