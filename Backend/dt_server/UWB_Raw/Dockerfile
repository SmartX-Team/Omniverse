# 기본 이미지로 Python 3.8 사용
FROM python:3.8-slim

# 작업 디렉토리 설정
WORKDIR /app

# 환경 변수 설정
ENV CONFIG_PATH /mnt/ceph-pvc/config.json

# requirements.txt 파일을 컨테이너로 복사
COPY requirements.txt /app/
#COPY config.json /app/
# 의존성 설치
RUN pip install --no-cache-dir -r requirements.txt

# 소스 코드를 컨테이너의 작업 디렉토리로 복사
COPY . /app/

# 애플리케이션 실행
CMD ["python", "db_collection.py"]
