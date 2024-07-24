import pygame
import sys
import math  # 수학 함수를 사용하기 위해 임포트

# Pygame 초기화
pygame.init()

# 화면 설정
size = width, height = 400, 400
screen = pygame.display.set_mode(size)
pygame.display.set_caption("Virtual Joystick")

# 색상 정의
black = (0, 0, 0)
white = (255, 255, 255)
red = (255, 0, 0)

# 조이스틱 파라미터
joystick_radius = 50
joystick_center = [200, 200]

def draw_joystick(position):
    """ 조이스틱과 중심을 그립니다. """
    screen.fill(black)  # 화면을 검은색으로 채움
    pygame.draw.circle(screen, red, joystick_center, joystick_radius + 10)  # 바깥 원
    pygame.draw.circle(screen, white, position, joystick_radius)  # 조이스틱 핸들
    pygame.display.flip()

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

# 초기 조이스틱 위치
draw_joystick(joystick_center)

# 이벤트 루프
running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.MOUSEMOTION:
            # 마우스가 조이스틱 주변에서 움직일 때만 조이스틱 위치 업데이트
            mouse_pos = pygame.mouse.get_pos()
            dx = mouse_pos[0] - joystick_center[0]
            dy = mouse_pos[1] - joystick_center[1]
            distance = math.sqrt(dx**2 + dy**2)
            if distance < joystick_radius:
                draw_joystick(mouse_pos)
                axes = calculate_axes(mouse_pos)
                print("Axes:", axes)  # 현재 축 값 출력

pygame.quit()
sys.exit()