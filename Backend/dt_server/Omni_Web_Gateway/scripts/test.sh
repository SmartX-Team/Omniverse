#!/bin/bash

echo "Running tests..."

# backend 디렉토리로 이동
cd backend

# 가상환경 활성화 (있는 경우) 
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

# 개발 의존성 설치
pip install -r requirements-dev.txt

# 테스트 실행
pytest tests/ -v --cov=app --cov-report=html

echo "Coverage report generated at backend/htmlcov/index.html"