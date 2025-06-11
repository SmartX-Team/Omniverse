import rclpy
from rclpy.node import Node

class AStarPlanner(Node):
    def __init__(self):
        super().__init__('a_star_planner')
        self.get_logger().info('A* Planner node has been started.')

def main(args=None):
    rclpy.init(args=args)
    node = AStarPlanner()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()