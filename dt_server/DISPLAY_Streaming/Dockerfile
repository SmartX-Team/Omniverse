# 베이스 이미지로 python의 공식 이미지 사용
FROM python:3.8-slim

# 작업 디렉토리 설정
WORKDIR /app

# 필요한 패키지 설치
RUN apt-get update && apt-get install -y \
    libopencv-core-dev \
    libopencv-imgproc-dev \
    libopencv-highgui-dev \
    scrot \
    python3-opencv \
    x11-xserver-utils \
    && rm -rf /var/lib/apt/lists/*

# 파이썬 라이브러리 설치
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 코드 추가
COPY . /app

# 환경 변수 설정
ENV DISPLAY=:0

# Flask 애플리케이션 실행
CMD ["python", "streaming.py"]
