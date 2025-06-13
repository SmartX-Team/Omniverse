import os
from glob import glob
from setuptools import find_packages, setup

package_name = 'ugv_nav'

setup(
    name=package_name,
    version='0.0.0',
    # find_packages()가 'ugv_nav/src' 폴더를 찾아 그 안의 파이썬 모듈들을 자동으로 포함
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob(os.path.join('launch', '*.launch.py'))),
        (os.path.join('share', package_name, 'config'), glob(os.path.join('config', '*.yaml'))),
        (os.path.join('lib', package_name, 'scripts'), glob(os.path.join('scripts', '*'))),
    ],
    install_requires=['setuptools', 'ament_index_python', 'rclpy'],
    zip_safe=True,
    maintainer='netai', 
    maintainer_email='inyong2327@gamil.com',
    description='TODO: Package description',
    license='TODO: License declaration',
    tests_require=['pytest'],
    # 'ros2 run <패키지명> <실행파일명>' 형태로 만들어줄 노드들을 지정
    entry_points={
        'console_scripts': [
            'rl_navigator = ugv_nav.rl_navigator_node:main',
            'a_star_planner = ugv_nav.a_star_planner:main',
            'health_check = ugv_nav.health_check:main',
        ],
    },
)