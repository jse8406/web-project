#!/bin/bash

# 1. Update & Install System Dependencies
echo "Installing system dependencies..."
sudo apt update
sudo apt install -y python3-pip python3-venv redis-server

# 2. Redis Setup
echo "Starting Redis..."
sudo systemctl enable redis-server
sudo systemctl start redis-server

# 3. Virtual Environment
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

# 4. Install Python Requirements
echo "Installing Python dependencies..."
source .venv/bin/activate
pip install -r requirements.txt

# 5. Migrations
echo "Running migrations..."
python manage.py migrate
python manage.py collectstatic --noinput

echo "Setup complete! Now configure the systemd service."
