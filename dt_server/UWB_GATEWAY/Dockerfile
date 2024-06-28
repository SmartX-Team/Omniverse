# 사용할 Python의 베이스 이미지
FROM python:3.9

# 작업 디렉토리 설정
WORKDIR /app

# 필요한 Python 라이브러리 설치
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 코드를 이미지 내부로 복사
COPY . .

# 컨테이너에서 실행될 명령어 설정
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
