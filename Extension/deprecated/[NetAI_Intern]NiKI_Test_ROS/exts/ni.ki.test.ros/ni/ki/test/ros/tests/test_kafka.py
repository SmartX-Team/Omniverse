from kafka import KafkaProducer
import json
import time

# Kafka Producer 설정
producer = KafkaProducer(
    bootstrap_servers=['10.80.0.3:9094'],  # Kafka 브로커 주소
    value_serializer=lambda v: json.dumps(v).encode('utf-8')  # JSON으로 직렬화 및 UTF-8 인코딩
)

print("Kafka Producer is running...")

# 카프카 서버 송신 테스트
detection_results = [
    {'id': 1, 'type': 'car', 'confidence': 0.01},
    {'id': 2, 'type': 'pedestrian', 'confidence': 0.89},
    {'id': 3, 'type': 'bicycle', 'confidence': 0.78}
]

# Message Produce
for result in detection_results:
    producer.send('test-topic', value=result)
    print(f"Sent detection result: {result}")
    time.sleep(0.1)  # waiting 100 ms

# 송신을 마치고 종료
producer.flush()
producer.close()