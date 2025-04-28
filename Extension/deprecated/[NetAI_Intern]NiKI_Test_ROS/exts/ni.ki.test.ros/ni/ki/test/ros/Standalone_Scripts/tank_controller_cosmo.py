# Cosmo - Controlled simulated motion
# Basic Imports
import pygame
from time import sleep, time

# Important Parameter
# Should the data be published to an ROS 2 Topic called "/ackermann_cmd"? (Recomended)
PUBLISH_TOPIC = True

# Should the data be published to an ROS 2 Topic calles "/cmd_vel"? (Recomended)
PUBLISH_VEL = True

# Distance from the front wheels to each other in meters
DISTANCE_BETWEEN_THE_FRONT_WHEELS = 0.421

# PLEASE DONT CHANGE THE NEXT PARAMETER - AUTOMATED
WHEEL_DISTANCE = DISTANCE_BETWEEN_THE_FRONT_WHEELS / 2

# Imports for publishing an ros2 topic
try:
    import rclpy
    from rclpy.node import Node
except ModuleNotFoundError:
    PUBLISH_TOPIC = False
    PUBLISH_VEL = False

try:
    from ackermann_msgs.msg import AckermannDriveStamped
except ModuleNotFoundError:
    PUBLISH_TOPIC = False

try:
    from geometry_msgs.msg import Twist
except ModuleNotFoundError:
    PUBLISH_VEL = False

# Additional Helper functions (for convenience purposes only - could run without)
WARNINGS_IMPORTED = True  # Can also be set to False to disable the warnings
try:
    import warnings
except ModuleNotFoundError:
    WARNINGS_IMPORTED = False

# Code written by Niki C. Zils for the purpose of using a Tank Controller for Husky
# Original Code for a Joystick was written by Inyong Song

# How to read the display
#  __     __
# |  |   |  |   ^ Anything above denotes a positive (+) velocity
# |  |   |  |   |
# |██|   |██|  <- The dots start out here - They show the current speed of the left and right side
# |  |   |  |   |
# |__|   |__|   V Anything below means a negative (-) velocity
#
#
# How it works
# As the main input source you use your mouse. (represented by this triangle: ▲)
# 
#  ____((______                                __     __
# |    _\\     |  With a left click the left  |  |   |  |
# |   |█|_|    |  wheel speed is determined.  |██| ▲ |  |
# |   |   |    |                              |  |   |██|
# |   |___|    |  Where as the right speed    |  |   |  |
# |____________|  stays untouched.            |__|   |__|
# 
# 
#  ____((______                                __     __
# |    _\\     |  With a right click the      |  |   |  |
# |   |_|█|    |  rigth wheel speed is        |██|   |  |
# |   |   |    |  determined.                 |  |   |  |
# |   |___|    |  Where as the left speed     |  |   |  |
# |____________|  stays untouched.            |__| ▲ |██|
# 
# 
#  ____((______                                __     __
# |    _\\     |  With a press on the mouse   |██| ▲ |██|
# |   |_█_|    |  wheel the speed on both     |  |   |  |
# |   |   |    |  sides gets changed to the   |  |   |  |
# |   |___|    |  same level.                 |  |   |  |
# |____________|                              |__|   |__|
# 
# It's important to note that this controller won't send any signal until both sides have been changed at least once.
# 
# TL;DR There also exist "Advanced Movement", which won't be explained here, since it requires additional buttons on
# the mouse. Try experimenting, if you want to use them or search via (Ctrl+F) for "Advanced Movement" in this script.
#


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
max_speed = 10

try:
    # Publisher
    class TankControllerPublisher(Node):
        def __init__(self):
            super().__init__('tank_controller_publisher')
            if PUBLISH_TOPIC:  # Ackermann Setup
                self.publisher_ = self.create_publisher(AckermannDriveStamped, 'ackermann_cmd', 10)
            
            if PUBLISH_VEL:  # Twist Setup
                self.publisher_vel_ = self.create_publisher(Twist, "cmd_vel", 10)

            self.timer = self.create_timer(0.1, self.timer_callback)
            self.input_pos1: float = None  # Left Drive Train
            self.input_pos2: float = None  # Right Drive Train

        def timer_callback(self):
            if self.input_pos1 and self.input_pos2:
                if PUBLISH_TOPIC:  # Ackermann
                    msg = AckermannDriveStamped()
                    msg.drive.acceleration = 0.0
                    msg.drive.speed = self.input_pos1
                    msg.drive.jerk = self.input_pos2  # This is a missusage of jerk as a second velocity parameter!!!
                    self.publisher_.publish(msg)
                    self.get_logger().info(f'Publishing: "{msg.drive}"')

                if PUBLISH_VEL:  # Twist
                    msg = Twist()
                    msg.linear.x = (self.input_pos1 + self.input_pos2)/2
                    msg.angular.z = (self.input_pos1 - self.input_pos2)/WHEEL_DISTANCE
                    self.publisher_vel_.publish(msg)
                    self.get_logger().info(f'Publishing: "{msg}"')

except NameError:  # This fails if the Import didn't succeded
    PUBLISH_TOPIC = False

# Main runs the joystick7
def main(args=None):
    if PUBLISH_TOPIC:
        rclpy.init(args=args)
        node = TankControllerPublisher()
    else:
        fail_message = "Failed to start up ROS2 Topic '/ackermann_cmd'!"
        if WARNINGS_IMPORTED:
            warnings.warn(fail_message)
        else:
            print(fail_message)
        # Starts outputing the values to the console
        print("L Vel|R Vel")

    # Pygame startup
    pygame.init()
    
    screen = pygame.display.set_mode(size)
    pygame.display.set_caption("Virtual Tank Controller - CoSMO")  # Contolled System Motion Overwatch

    def draw_joysticks(pos_1, pos_2):
        screen.fill(black)
        joystick_cx, joystick_cy = joystick_center
        # Draws the neccesarry circles
        pygame.draw.circle(screen, red, [joystick_cx//2, 3*joystick_cy//4], joystick_radius + 10)
        pygame.draw.circle(screen, red, [3*joystick_cx//2, 3*joystick_cy//4], joystick_radius + 10)
        pygame.draw.circle(screen, red, [joystick_cx//2, 5*joystick_cy//4], joystick_radius + 10)
        pygame.draw.circle(screen, red, [3*joystick_cx//2, 5*joystick_cy//4], joystick_radius + 10)

        # Connects them via rectangels
        pygame.draw.rect(screen, red, [joystick_cx//4-10, 3*joystick_cy//4, joystick_cx//2+20, 2*joystick_cy//4])
        pygame.draw.rect(screen, red, [5*joystick_cx//4-10, 3*joystick_cy//4, joystick_cx//2+20, 2*joystick_cy//4])

        # Draws the actuall joysticks
        # 1 Pos
        pygame.draw.circle(screen, white, [joystick_cx//2, pos_1], joystick_radius)

        # 2 Pos
        pygame.draw.circle(screen, white, [3*joystick_cx//2, pos_2], joystick_radius)

        # Draws the resulting screen
        pygame.display.flip()


    draw_joysticks(joystick_center[1], joystick_center[1])
    try:
        # 이벤트 루프
        running = True
        st_time = time()
        pos_1 = joystick_center[1]
        pos_2 = joystick_center[1]
        while running: # and rclpy.ok():  # <- Can be added for further accuracy of the loop
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    mouse_pos = list(pygame.mouse.get_pos())
                    mouse_y = mouse_pos[1]
                    clamp = [3*joystick_center[1]//4-joystick_radius, 5*joystick_center[1]//4+joystick_radius]

                    if clamp[0] < mouse_y < clamp[1]:
                        if event.button == 1:  # Left click
                            pos_1 = mouse_y
                        elif event.button == 3:  # Right click
                            pos_2 = mouse_y
                        elif event.button == 2:  # Click on the Mouse wheel
                            pos_1 = mouse_y
                            pos_2 = mouse_y

                        # Keyword for searching: Advanced Movement
                        
                        # Advanced Moves might not work for every mouse, since they require more button
                        elif event.button == 6:  # Makes a rotation over one Axis - Advanced Move
                            pos_1 = 2*joystick_center[1] - mouse_y
                            pos_2 = mouse_y
                        elif event.button == 7:  # Makes a rotation over the other Axis - Advanced Move
                            pos_1 = mouse_y
                            pos_2 = 2*joystick_center[1] - mouse_y
                        
                        # If a button is presed for which no action is configured it will exit the loop
                        else:
                            break
                        draw_joysticks(pos_1, pos_2)

                        # Get Delta
                        d1 = joystick_center[1] - pos_1
                        d2 = joystick_center[1] - pos_2

                        # Normalize
                        n1 = d1 / (joystick_radius+joystick_center[1]//4)
                        n2 = d2 / (joystick_radius+joystick_center[1]//4)

                        if PUBLISH_TOPIC or PUBLISH_VEL:
                            # Setup
                            node.input_pos1 = float(n1) * max_speed
                            node.input_pos2 = float(n2) * max_speed

                            # Publish
                            rclpy.spin_once(node)
                        else:
                            # Prints it into the console
                            print(round(float(n1) * max_speed, 3), end=" ")
                            if n1 >= 0:
                                print(end=" ")
                            print("|", round(float(n2) * max_speed, 3))

                        # Wait
                        sleep(0.1)

            if time() >= st_time + 0.2:
                if PUBLISH_TOPIC or PUBLISH_VEL:
                    rclpy.spin_once(node)
                else:
                    print('  "  |  "  ')
                st_time = time()
                sleep(0.1)

    except KeyboardInterrupt:
        pass

    pygame.quit()

    if PUBLISH_TOPIC:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
