"""

--- 작성일 :2024.05.04 송인용 ---

Flask 와 비동기 처리 로직이 생각보다 불편하길래 일단 해당 코드에서 새로 비동기 대신 간단하게 forward, backward 메시지랑 시간 보내면 로봇이 맞춰서 움직이도록 했다.

--- 작성일 :2024.05.03 송인용 ---

기존에 구현한 TeleOperation 코드를 응용하여, 데이터 수집의 정확성을 높히기 위해 로봇을 동일한 경로로 이동할려고 만든 코드이다.
안전을 위해 해당 기능으로 로봇을 움직일려면 먼저 사용자가 직접 로봇 ROS에서 움직임 로직을 처리하는 Node를 활성화 해줘야한다.

임시로 데이터 확보하기 편하라고 만든 기능으로 비동기 처리는 실제 사용 로직에서 알아서 구현

"""
import json
import asyncio
from aiokafka import AIOKafkaProducer
from confluent_kafka import Producer


class RobotControllerByCommands:
    def __init__(self, config_path):
        self.config_path = config_path
        self.producer = None
        self.topic = None
        self._load_config_and_initialize()

    def _load_config_and_initialize(self):
        """ 설정 파일을 로드하고 Kafka 프로듀서를 초기화합니다. """
        with open(self.config_path, 'r') as file:
            config_file = json.load(file)
        
        self.producer = Producer({
            'bootstrap.servers': config_file['robot_control']['bootstrap_servers']
        })
        self.topic = config_file['robot_control']['topic']

    def send_command(self, command, duration):
        """ 로봇 제어 명령을 Kafka 토픽으로 보냅니다. """
        command_message = json.dumps({
            'command': command,
            'duration': duration
        })
        self.producer.produce(self.topic, command_message, callback=self.delivery_report)
        self.producer.flush()  # 보장된 전송을 위해 flush() 호출
        print(f"Sent command to {self.topic}: {command_message}")

    def delivery_report(self, err, msg):
        """ 메시지 전송 상태를 보고합니다. """
        if err is not None:
            print(f'Message delivery failed: {err}')
        else:
            print(f'Message delivered to {msg.topic()} [{msg.partition()}]')

    def close_producer(self):
        """ 프로듀서를 정리합니다. """
        self.producer.flush()
        print("Kafka producer closed.")


class RobotController:
    def __init__(self, config_path):
        self.config_path = config_path
        self.producer = None

    async def initialize_producer(self):
        
        with open(self.config_path, 'r') as file:
            config_file = json.load(file)

        self.producer = AIOKafkaProducer(
            bootstrap_servers=config_file['robot_control']['bootstrap_servers'],
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            loop=asyncio.get_running_loop()
        )
        await self.producer.start()

        """
        Kafka 프로듀서를 초기화하고 주제를 설정한다.
        
        :param bootstrap_servers: Kafka 서버의 주소 리스트
        :param topic: 메시지를 보낼 Kafka 토픽
        """

        self.topic = config_file['robot_control']['topic']
        self.commands = {
            'forward': [0, 1],
            'backward': [0, -1]
        }

    async def send_movement_command(self, command_type, duration):
        if self.producer is None:
            await self.initialize_producer()

        axes = self.commands.get(command_type)
        if not axes:
            print(f"Invalid command type: {command_type}")
            return

        async with self.producer:
            start_time = asyncio.get_running_loop().time()
            while asyncio.get_running_loop().time() - start_time < duration:
                await self.producer.send_and_wait(self.topic, {'axes': axes})
                await asyncio.sleep(0.06)

    async def close_producer(self):
        if self.producer:
            await self.producer.stop()
            self.producer = None