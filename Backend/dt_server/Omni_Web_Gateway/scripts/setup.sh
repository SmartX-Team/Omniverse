echo "Setting up Omni Web Gateway development environment..."

# backend 디렉토리로 이동
cd backend

# 가상환경 생성 (선택사항)
if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv venv
fi

# 가상환경 활성화 (Linux/Mac)
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
    echo "Virtual environment activated"
fi

# 의존성 설치
echo "Installing dependencies..."
pip install -r requirements.txt

# 환경변수 파일 생성
if [ ! -f ".env" ]; then
    echo "Creating environment file..."
    cp .env.example .env
    echo ".env file created. Modify if needed."
fi

echo "Setup complete! Run 'cd backend && python3 -m app.main' or './scripts/run_dev.sh' to start the server."