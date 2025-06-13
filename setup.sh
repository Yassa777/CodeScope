#!/bin/bash

# Create virtual environment for backend
echo "Setting up Python virtual environment..."
python -m venv venv
source venv/bin/activate

# Install backend dependencies
echo "Installing backend dependencies..."
cd backend
pip install -r requirements.txt
cd ..

# Install frontend dependencies
echo "Installing frontend dependencies..."
cd frontend
npm install
cd ..

# Create necessary directories
echo "Creating cache directory..."
mkdir -p /tmp/halos_cache

echo "Setup complete! To start the application:"
echo "1. Start the backend server:"
echo "   cd backend"
echo "   source ../venv/bin/activate"
echo "   uvicorn app.main:app --reload"
echo ""
echo "2. In a new terminal, start the frontend:"
echo "   cd frontend"
echo "   npm run dev"
echo ""
echo "3. Open http://localhost:5173 in your browser" 