#!/bin/bash

# Financial Planning Application Development Setup Script
# This script sets up the development environment for the financial planning application

set -e  # Exit on any error

echo "=== Financial Planning Application Development Setup ==="
echo ""

# Check if we're in the right directory
if [ ! -f "Makefile" ] || [ ! -d "backend" ] || [ ! -d "frontend" ]; then
    echo "❌ Error: This script must be run from the project root directory"
    echo "   Make sure you're in the financial-planning directory"
    exit 1
fi

echo "✅ Project structure verified"

# Check for required tools
echo ""
echo "🔍 Checking required tools..."

# Check Python
if ! command -v python &> /dev/null; then
    echo "❌ Python is not installed or not in PATH"
    exit 1
fi
echo "✅ Python found: $(python --version)"

# Check pip
if ! command -v pip &> /dev/null; then
    echo "❌ pip is not installed or not in PATH"
    exit 1
fi
echo "✅ pip found: $(pip --version)"

# Check Node.js
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is not installed or not in PATH"
    exit 1
fi
echo "✅ Node.js found: $(node --version)"

# Check npm
if ! command -v npm &> /dev/null; then
    echo "❌ npm is not installed or not in PATH"
    exit 1
fi
echo "✅ npm found: $(npm --version)"

# Check make
if ! command -v make &> /dev/null; then
    echo "❌ make is not installed or not in PATH"
    exit 1
fi
echo "✅ make found"

echo ""
echo "🚀 Installing dependencies..."

# Install all dependencies
echo ""
echo "📦 Installing backend dependencies..."
make install-backend

echo ""
echo "📦 Installing frontend dependencies..."
make install-frontend

echo ""
echo "🧪 Testing setup..."

# Test backend import
echo "Testing backend app import..."
cd backend
python -c "from main import app; print('✅ Backend imports successfully')" || {
    echo "❌ Backend import failed"
    exit 1
}
cd ..

echo ""
echo "🎉 Setup completed successfully!"
echo ""
echo "Available commands:"
echo "  make dev          - Start both backend and frontend in development mode"
echo "  make start        - Alias for dev"
echo "  make dev-backend  - Start only backend development server (http://localhost:8000)"
echo "  make dev-frontend - Start only frontend development server (http://localhost:5173)"
echo "  make install      - Install all dependencies"
echo "  make test         - Run backend tests"
echo "  make clean        - Clean up build artifacts"
echo "  make help         - Show help message"
echo ""
echo "Next steps:"
echo "1. Run 'make dev' to start both servers"
echo "2. Visit http://localhost:5173 for the frontend"
echo "3. Visit http://localhost:8000/docs for the API documentation"
echo "4. Database tables are automatically created on first run"
echo ""
echo "Happy coding! 🎯"