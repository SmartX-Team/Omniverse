import pygame
import math  # 수학 함수를 사용하기 위해 임포트
import rclpy
from rclpy.node import Node
from ackermann_msgs.msg import AckermannDriveStamped
from time import sleep, time

# Adapted and extended by Niki C. Zils
# Original Code from Inyong Song

# Important Parametres
# 화면 설정
size = width, height = 400, 400

# 색상 정의
black = (0, 0, 0)
white = (255, 255, 255)
red = (255, 0, 0)

# 조이스틱 파라미터
joystick_radius = 50
joystick_center = [200, 200]

# Maximum Speed
max_speed = 10**2

# Publisher
class JoystickPublisher(Node):
    def __init__(self):
        super().__init__('joystick_publisher')
        self.publisher_ = self.create_publisher(AckermannDriveStamped, 'ackermann_cmd', 10)
        self.timer = self.create_timer(0.1, self.timer_callback)
        self.input_float: float = None

    def timer_callback(self):
        if self.input_float:
            msg = AckermannDriveStamped()
            msg.drive.acceleration = self.input_float
            msg.drive.speed = self.input_float
            self.publisher_.publish(msg)
            self.get_logger().info(f'Publishing: "{msg.drive.acceleration}"')
            # self.input_float = None

# Calulates Axes
def calculate_axes(mouse_pos):
        """ 마우스 위치로부터 조이스틱 축 값 계산 """
        dx = mouse_pos[0] - joystick_center[0]
        dy = joystick_center[1] - mouse_pos[1]  # Y축은 화면 좌표와 반대
        distance = math.sqrt(dx**2 + dy**2)
        max_distance = joystick_radius

        # 조이스틱 최대 범위 내에서의 거리 비율 계산
        if distance > max_distance:
            distance = max_distance

        # 축 값을 -1.0에서 1.0 사이의 값으로 스케일
        normalized_x = dx / max_distance
        normalized_y = dy / max_distance

        return [normalized_x, normalized_y]

# Main runs the joystick7
def main(args=None):
    rclpy.init(args=args)
    node = JoystickPublisher()

    # Pygame 초기화
    pygame.init()
    
    screen = pygame.display.set_mode(size)
    pygame.display.set_caption("Virtual Joystick")

    def draw_joystick(position):
        """ 조이스틱과 중심을 그립니다. """
        screen.fill(black)  # 화면을 검은색으로 채움
        pygame.draw.circle(screen, red, joystick_center, joystick_radius + 10)  # 바깥 원
        pygame.draw.circle(screen, white, position, joystick_radius)  # 조이스틱 핸들
        pygame.display.flip()

    try:
        # 이벤트 루프
        running = True
        st_time = time()
        while running and rclpy.ok():
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    # 마우스가 조이스틱 주변에서 움직일 때만 조이스틱 위치 업데이트
                    mouse_pos = pygame.mouse.get_pos()
                    dx = mouse_pos[0] - joystick_center[0]
                    dy = mouse_pos[1] - joystick_center[1]
                    distance = math.sqrt(dx**2 + dy**2)
                    if distance < joystick_radius:
                        draw_joystick(mouse_pos)
                        axes = calculate_axes(mouse_pos)

                        node.input_float = axes[1] * max_speed
                        rclpy.spin_once(node)
                        sleep(0.1)

                        # print("Axes:", axes)  # 현재 축 값 출력
            if time() >= st_time + 0.2:
                rclpy.spin_once(node)
                st_time = time()
                sleep(0.1)

    except KeyboardInterrupt:
        pass
    pygame.quit()
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
