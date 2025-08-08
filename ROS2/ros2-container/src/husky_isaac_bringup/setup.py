import os
from glob import glob
from setuptools import setup

package_name = 'husky_isaac_bringup'

setup(
    name=package_name,
    version='0.0.1',
    packages=[], 
    py_modules=[
        'scripts.isaac_bridge',
        'scripts.auto_init_pose',
    ],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        # launch 폴더 안의 모든 .launch.py 파일을 설치 경로에 복사
        (os.path.join('share', package_name, 'launch'), glob('launch/*.launch.py')),
        # config 폴더 안의 모든 .yaml, .xml 파일을 설치 경로에 복사
        (os.path.join('share', package_name, 'config'), glob('config/*.yaml')),
        (os.path.join('share', package_name, 'config'), glob('config/*.xml')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='netai',
    maintainer_email='netai@example.com',
    description='ROS 2 bringup package for Husky robot in Isaac Sim.',
    license='Apache-2.0',
    tests_require=['pytest'],

    entry_points={
        'console_scripts': [
            'isaac_bridge = scripts.isaac_bridge:main',
            'auto_init_pose = scripts.auto_init_pose:main',
        ],
    },
)