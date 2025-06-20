# NetAI UWB Real-time Tracking Extension

실시간 UWB 추적 시스템을 위한 25년도 버전으로 업데이트된 Omniverse Extension입니다.

## 설치 및 설정

### 1. 의존성 설치
Extension은 다음 Python 패키지들을 의존합니다.
- `requests>=2.25.0`
- `httpx>=0.24.0`
- `aiokafka>=0.8.0`
- `psycopg2-binary>=2.9.0`
- `numpy>=1.21.0`

### 2. 설정 파일 생성
Extension 코드들은 보통 컨테이너들과 달리 config.json 형태로 의존성 정보를 주입합니다.
`uwbrtls/config.json.example`을 복사하여 `uwbrtls/config.json`을 생성하고 환경에 맞게 수정하세요.

```bash
cp uwbrtls/config.json.example uwbrtls/config.json