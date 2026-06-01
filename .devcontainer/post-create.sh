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
