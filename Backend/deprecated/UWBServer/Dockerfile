FROM python:3.8

# 작업 디렉터리 설정
WORKDIR /usr/src/app

# 필요한 Python 라이브러리 설치
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Python 스크립트 복사
COPY . .

# 환경 변수 설정
ENV REDIS_HOST=10.32.187.108

# 컨테이너 실행 시 실행할 명령어
CMD ["python", "./uwbserver.py"]
