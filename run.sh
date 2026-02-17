#!/bin/bash
# Quick launcher for the Pathway Testing Dashboard

echo "🚀 Starting Pathway Regression Testing Dashboard..."
echo ""

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "⚠️  Virtual environment not found. Creating one..."
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
else
    source .venv/bin/activate
fi

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "⚠️  .env file not found. Please create one with your API keys."
    echo ""
    echo "Required variables:"
    echo "  OPENROUTER_API_KEY=your_key"
    echo "  OPENROUTER_BASE_URL=https://openrouter.ai/api/v1"
    echo "  BLAND_API_KEY=your_key"
    echo ""
    exit 1
fi

echo "✅ Environment ready!"
echo ""
echo "Opening dashboard at http://localhost:8501"
echo "Press Ctrl+C to stop"
echo ""

streamlit run app.py
