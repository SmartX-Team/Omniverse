#!/usr/bin/env python3
import pygame
import sys
import math
import time

# +++ ROS2 import 수정 +++
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist # AckermannDriveStamped 대신 Twist 사용
# ++++++++++++++++++++++

# --- 설정값 ---
NODE_NAME = 'virtual_joystick_twist_publisher'
TOPIC_NAME = '/cmd_vel' # Isaac Sim OmniGraph가 구독하는 /cmd_vel 토픽

# --- !!! 속도 설정 !!! ---
TARGET_LINEAR_SPEED_LOW = 0.3   # 예시: 저속 선속도 (m/s)
TARGET_LINEAR_SPEED_MEDIUM = 0.5 # 예시: 중속 선속도 (m/s)
TARGET_LINEAR_SPEED_HIGH = 1.0  # 예시: 고속 선속도 (m/s)

TARGET_ANGULAR_SPEED_LOW = 0.3  # 예시: 저속 각속도 (rad/s)
TARGET_ANGULAR_SPEED_MEDIUM = 0.5 # 예시: 중속 각속도 (rad/s)
TARGET_ANGULAR_SPEED_HIGH = 1.0 # 예시: 고속 각속도 (rad/s)

# ===> 현재 적용할 최대 속도를 여기서 선택하세요! <===
CURRENT_MAX_LINEAR_SPEED = TARGET_LINEAR_SPEED_HIGH
CURRENT_MAX_ANGULAR_SPEED = TARGET_ANGULAR_SPEED_MEDIUM
# =============================================

PUBLISH_RATE = 30 # 초당 발행 빈도 (Hz)

# Pygame 초기화 (기존과 동일)
pygame.init()
pygame.font.init() 
status_font = pygame.font.SysFont('Consolas', 18)
size = width, height = 400, 400
screen = pygame.display.set_mode(size)
pygame.display.set_caption(f"Virtual Joystick -> {TOPIC_NAME} | Max Lin: {CURRENT_MAX_LINEAR_SPEED:.1f} m/s, Max Ang: {CURRENT_MAX_ANGULAR_SPEED:.1f} rad/s")

black = (0, 0, 0)
white = (255, 255, 255)
red = (255, 0, 0)
green = (0, 255, 0)
joystick_radius = 50
joystick_center = [width // 2, height // 2]

# --- ROS2 Node 클래스 (Twist 메시지용으로 수정) ---
class VirtualJoystickPublisher(Node):
    def __init__(self):
        super().__init__(NODE_NAME)
        self.publisher_ = self.create_publisher(Twist, TOPIC_NAME, 10) # Twist 메시지 타입 사용
        self.get_logger().info(f"'{NODE_NAME}' started.")
        self.get_logger().info(f"Publishing Twist to '{TOPIC_NAME}'")
        self.get_logger().info(f"Using MAX Linear Speed: {CURRENT_MAX_LINEAR_SPEED:.1f} m/s, Max Angular Speed: {CURRENT_MAX_ANGULAR_SPEED:.1f} rad/s")

    def publish_command(self, linear_x, angular_z):
        """Twist 메시지를 생성하고 발행합니다."""
        msg = Twist()
        # geometry_msgs/Vector3
        msg.linear.x = float(linear_x)
        msg.linear.y = 0.0
        msg.linear.z = 0.0
        # geometry_msgs/Vector3
        msg.angular.x = 0.0
        msg.angular.y = 0.0
        msg.angular.z = float(angular_z)
        
        self.publisher_.publish(msg)

# --- Helper 함수 (draw_joystick 수정 - 표시 텍스트 변경) ---
def draw_joystick(position, current_linear_x, current_angular_z_rad):
    screen.fill(black)
    pygame.draw.circle(screen, red, joystick_center, joystick_radius + 10, 1)
    pygame.draw.line(screen, red, (joystick_center[0], joystick_center[1]-joystick_radius-10), (joystick_center[0], joystick_center[1]+joystick_radius+10), 1)
    pygame.draw.line(screen, red, (joystick_center[0]-joystick_radius-10, joystick_center[1]), (joystick_center[0]+joystick_radius+10, joystick_center[1]), 1)
    pygame.draw.circle(screen, white, position, joystick_radius)

    try:
        linear_text = f"Linear Vel X: {current_linear_x:+.2f} m/s"
        angular_text = f"Angular Vel Z: {math.degrees(current_angular_z_rad):+.1f} deg/s" # 각도를 도(degree)로 표시
        max_lin_text = f"Max Lin Speed: {CURRENT_MAX_LINEAR_SPEED:.1f} m/s"
        max_ang_text = f"Max Ang Speed: {math.degrees(CURRENT_MAX_ANGULAR_SPEED):.1f} deg/s"


        text_surface_lin = status_font.render(linear_text, True, green)
        text_surface_ang = status_font.render(angular_text, True, green)
        text_surface_max_lin = status_font.render(max_lin_text, True, white)
        text_surface_max_ang = status_font.render(max_ang_text, True, white)


        screen.blit(text_surface_max_lin, (10, 10))
        screen.blit(text_surface_max_ang, (10, 30))
        screen.blit(text_surface_lin, (10, 50))
        screen.blit(text_surface_ang, (10, 70))
    except Exception as e:
        print(f"Error rendering font: {e}")

    pygame.display.flip()

def calculate_axes(mouse_pos):
    dx = mouse_pos[0] - joystick_center[0]
    dy = joystick_center[1] - mouse_pos[1] 
    distance = math.sqrt(dx**2 + dy**2)
    max_distance = float(joystick_radius)

    if distance == 0:
        return [0.0, 0.0], list(joystick_center)

    if distance > max_distance:
        scale = max_distance / distance
        dx *= scale
        dy *= scale
        clamped_pos = [int(joystick_center[0] + dx), int(joystick_center[1] - dy)]
    else:
        clamped_pos = list(mouse_pos)

    normalized_x = dx / max_distance
    normalized_y = dy / max_distance 

    deadzone = 0.05
    if abs(normalized_x) < deadzone: normalized_x = 0.0
    if abs(normalized_y) < deadzone: normalized_y = 0.0

    return [normalized_x, normalized_y], clamped_pos

# --- 메인 로직 (Twist 메시지용으로 수정) ---
def main(args=None):
    rclpy.init(args=args)
    node = VirtualJoystickPublisher()

    current_joystick_pos = list(joystick_center)
    current_axes = [0.0, 0.0]
    is_dragging = False
    clock = pygame.time.Clock()

    current_linear_x = 0.0
    current_angular_z = 0.0

    try:
        while rclpy.ok():
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    raise KeyboardInterrupt
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:
                        mouse_pos = pygame.mouse.get_pos()
                        dx = mouse_pos[0] - joystick_center[0]
                        dy = mouse_pos[1] - joystick_center[1]
                        distance = math.sqrt(dx**2 + dy**2)
                        if distance <= joystick_radius:
                            is_dragging = True
                            current_axes, current_joystick_pos = calculate_axes(mouse_pos)
                elif event.type == pygame.MOUSEBUTTONUP:
                    if event.button == 1:
                        is_dragging = False
                        current_axes = [0.0, 0.0]
                        current_joystick_pos = list(joystick_center)
                elif event.type == pygame.MOUSEMOTION:
                    if is_dragging:
                        mouse_pos = pygame.mouse.get_pos()
                        current_axes, current_joystick_pos = calculate_axes(mouse_pos)

            # 축 값을 Twist 명령으로 변환
            # current_axes[1] (Y축 값, 위가 +)을 linear.x 로 사용
            current_linear_x = current_axes[1] * CURRENT_MAX_LINEAR_SPEED
            # current_axes[0] (X축 값, 오른쪽이 +)을 angular.z 로 사용 (방향 반전하여 왼쪽 조향이 +angular.z 되도록)
            current_angular_z = -current_axes[0] * CURRENT_MAX_ANGULAR_SPEED

            node.publish_command(current_linear_x, current_angular_z)
            draw_joystick(current_joystick_pos, current_linear_x, current_angular_z) # angular_z는 라디안 값 전달

            rclpy.spin_once(node, timeout_sec=0.0)
            clock.tick(PUBLISH_RATE)

    except KeyboardInterrupt:
        print("\nCtrl+C detected. Exiting...")
    except Exception as e:
        print(f"\nAn error occurred: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("\nCleaning up...")
        if 'node' in locals() and node:
            print("Sending stop command (Twist)...")
            node.publish_command(0.0, 0.0) # 선속도 0, 각속도 0으로 정지
            time.sleep(0.2)
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
        pygame.quit()
        print("Cleanup complete. Exited.")
        sys.exit()

if __name__ == '__main__':
    main()