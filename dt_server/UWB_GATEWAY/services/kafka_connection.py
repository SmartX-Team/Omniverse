import json
from aiokafka import AIOKafkaProducer
import os


"""싱글톤 패턴으로 Kafka 접속정보 유지"""
class KafkaClientSingleton:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            # __new__에서 초기화하는건 좋은 방법은 아니라고 하던데, 일단 빨리 좀 연구에 집중하려고 여기에다가 설정값 불러옴
            try:
                cls._instance.load_config()
            except Exception as e:
                    print(f"Failed to load config: {e}")
                    cls._instance = None  # 설정 로드 실패 시 인스턴스 생성 취소
        return cls._instance
    
    def load_config(self):
        config_path = os.getenv('CONFIG_PATH', '/home/netai/Omniverse/dt_server/UWB_EKF/config.json')
        with open(config_path, 'r') as file:
            self.config = json.load(file)

    async def start(self):
        self.producer = AIOKafkaProducer(
            bootstrap_servers=self.config['kafka_server'],
            value_serializer=lambda x: json.dumps(x).encode('utf-8')
        )
        # producer를 시작합니다. start()는 비동기 메소드이므로 await을 사용해야 합니다.
        await self.producer.start()

    async def send_message(self, topic, message):
        """메시지를 Kafka 토픽에 비동기적으로 전송."""
        await self.producer.send_and_wait(topic, message)

    async def stop(self):
        
        await self.producer.stop()