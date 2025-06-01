"""
FROM Gemini and Claude 4 ~~~~

"""

#!/usr/bin/env python3
import pygame
import sys
import math
import time
import json
import os
import uuid

# --- Kafka-Python 라이브러리 임포트 ---
# pip install kafka-python pygame
try:
    from kafka import KafkaProducer
    from kafka.errors import KafkaError
except ImportError:
    print("ERROR: 필요한 라이브러리가 설치되지 않았습니다.")
    print("Please install it using: pip install kafka-python pygame")
    exit(1)

# --- 환경 변수 로드 ---
KAFKA_BROKER_ADDRESS = os.environ.get('KAFKA_BROKER_ADDRESS', '10.79.1.1:9094')
KAFKA_PRODUCER_TOPIC = os.environ.get('KAFKA_PRODUCER_TOPIC', 'inyong-joystick')

# --- 속도 설정 ---
TARGET_LINEAR_SPEED_LOW = 0.3
TARGET_LINEAR_SPEED_MEDIUM = 0.5
TARGET_LINEAR_SPEED_HIGH = 5.0

TARGET_ANGULAR_SPEED_LOW = 0.5
TARGET_ANGULAR_SPEED_MEDIUM = 1.0
TARGET_ANGULAR_SPEED_HIGH = 1.5

# ===> 현재 적용할 최대 속도를 여기서 선택하세요! <===
CURRENT_MAX_LINEAR_SPEED = TARGET_LINEAR_SPEED_MEDIUM
CURRENT_MAX_ANGULAR_SPEED = TARGET_ANGULAR_SPEED_MEDIUM

# Pygame 및 Kafka Producer 초기화
print("--- Pygame to Kafka Joystick ---")
print(f"KAFKA_BROKER_ADDRESS: {KAFKA_BROKER_ADDRESS}")
print(f"KAFKA_PRODUCER_TOPIC: {KAFKA_PRODUCER_TOPIC}")
print("--------------------------------")

pygame.init()
pygame.font.init()
status_font = pygame.font.SysFont('Consolas', 18)
size = width, height = 400, 400
screen = pygame.display.set_mode(size)
pygame.display.set_caption(f"Joystick -> Kafka: {KAFKA_PRODUCER_TOPIC}")

black, white, red, green = (0, 0, 0), (255, 255, 255), (255, 0, 0), (0, 255, 0)
joystick_radius = 50
joystick_center = [width // 2, height // 2]

def draw_joystick(position, current_linear_x, current_angular_z_rad):
    screen.fill(black)
    pygame.draw.circle(screen, red, joystick_center, joystick_radius + 10, 1)
    pygame.draw.line(screen, red, (joystick_center[0], joystick_center[1]-joystick_radius-10), (joystick_center[0], joystick_center[1]+joystick_radius+10), 1)
    pygame.draw.line(screen, red, (joystick_center[0]-joystick_radius-10, joystick_center[1]), (joystick_center[0]+joystick_radius+10, joystick_center[1]), 1)
    pygame.draw.circle(screen, white, position, joystick_radius)

    linear_text = f"Linear Vel X: {current_linear_x:+.2f} m/s"
    angular_text = f"Angular Vel Z: {math.degrees(current_angular_z_rad):+.1f} deg/s"
    max_lin_text = f"Max Lin Speed: {CURRENT_MAX_LINEAR_SPEED:.1f} m/s"
    max_ang_text = f"Max Ang Speed: {math.degrees(CURRENT_MAX_ANGULAR_SPEED):.1f} deg/s"

    screen.blit(status_font.render(max_lin_text, True, white), (10, 10))
    screen.blit(status_font.render(max_ang_text, True, white), (10, 30))
    screen.blit(status_font.render(linear_text, True, green), (10, 50))
    screen.blit(status_font.render(angular_text, True, green), (10, 70))
    
    pygame.display.flip()

def calculate_axes(mouse_pos):
    dx = mouse_pos[0] - joystick_center[0]
    dy = joystick_center[1] - mouse_pos[1]
    distance = math.sqrt(dx**2 + dy**2)
    max_distance = float(joystick_radius)

    if distance == 0: return [0.0, 0.0], list(joystick_center)
    if distance > max_distance:
        scale = max_distance / distance
        dx *= scale; dy *= scale
        clamped_pos = [int(joystick_center[0] + dx), int(joystick_center[1] - dy)]
    else:
        clamped_pos = list(mouse_pos)

    normalized_x = dx / max_distance
    normalized_y = dy / max_distance
    deadzone = 0.05
    if abs(normalized_x) < deadzone: normalized_x = 0.0
    if abs(normalized_y) < deadzone: normalized_y = 0.0
    return [normalized_x, normalized_y], clamped_pos

def main():
    # --- Kafka 프로듀서 초기화 ---
    producer = None
    try:
        producer = KafkaProducer(
            bootstrap_servers=KAFKA_BROKER_ADDRESS.split(','),
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        print(f"KafkaProducer connected to {KAFKA_BROKER_ADDRESS}")
    except KafkaError as e:
        print(f"FATAL: KafkaProducer connection FAILED: {e}")
        pygame.quit()
        sys.exit()

    current_joystick_pos = list(joystick_center)
    is_dragging = False
    clock = pygame.time.Clock()

    try:
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    raise KeyboardInterrupt
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mouse_pos = pygame.mouse.get_pos()
                    distance = math.hypot(mouse_pos[0] - joystick_center[0], mouse_pos[1] - joystick_center[1])
                    if distance <= joystick_radius:
                        is_dragging = True
                elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                    is_dragging = False
                elif event.type == pygame.MOUSEMOTION and is_dragging:
                    pass # 드래그 중에는 아래에서 위치를 계속 갱신

            if is_dragging:
                current_axes, current_joystick_pos = calculate_axes(pygame.mouse.get_pos())
            else:
                current_axes, current_joystick_pos = [0.0, 0.0], list(joystick_center)
            
            # 축 값을 속도 명령으로 변환
            current_linear_x = current_axes[1] * CURRENT_MAX_LINEAR_SPEED
            current_angular_z = -current_axes[0] * CURRENT_MAX_ANGULAR_SPEED

            # --- Kafka로 메시지 발행 ---
            # 컨슈머가 받을 수 있는 JSON 형식으로 페이로드 생성
            payload = {
                "linear": {
                    "x": current_linear_x, "y": 0.0, "z": 0.0
                },
                "angular": {
                    "x": 0.0, "y": 0.0, "z": current_angular_z
                }
            }
            # Kafka 토픽으로 전송
            producer.send(KAFKA_PRODUCER_TOPIC, value=payload)
            print(f"Sent to Kafka: linear_x={current_linear_x:.2f}, angular_z={current_angular_z:.2f}", end='\r')

            draw_joystick(current_joystick_pos, current_linear_x, current_angular_z)
            clock.tick(30) # 30Hz로 루프 속도 제어

    except KeyboardInterrupt:
        print("\nCtrl+C detected. Exiting...")
    except Exception as e:
        print(f"\nAn error occurred: {e}")
    finally:
        print("\nCleaning up...")
        if producer:
            # 마지막으로 정지 신호 전송
            stop_payload = {"linear": {"x": 0.0, "y": 0.0, "z": 0.0}, "angular": {"x": 0.0, "y": 0.0, "z": 0.0}}
            try:
                producer.send(KAFKA_PRODUCER_TOPIC, value=stop_payload).get(timeout=5)
                print("Stop command sent to Kafka.")
                producer.flush(timeout=5.0)
                producer.close(timeout=5.0)
                print("Kafka producer closed.")
            except KafkaError as e:
                print(f"Error while sending stop command or closing producer: {e}")
        pygame.quit()
        print("Pygame quit. Exited.")
        sys.exit()

if __name__ == '__main__':
    main()