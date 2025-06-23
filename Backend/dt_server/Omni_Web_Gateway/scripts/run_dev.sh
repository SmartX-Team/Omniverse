#!/bin/bash


echo "Starting Omni Web Gateway development server..."

# backend 디렉토리로 이동
cd backend

# 가상환경 활성화 (있는 경우)
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

# 개발 서버 실행
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --log-level info