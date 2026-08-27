import os
from glob import glob
from setuptools import setup

package_name = 'iot_rf_receiver'

setup(
    name=package_name,
    version='1.0.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.launch.py')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='you',
    maintainer_email='you@example.com',
    description='NRF24L01 -> API + ROS 토픽 수신 노드',
    license='MIT',
    entry_points={
        'console_scripts': [
            'receiver = iot_rf_receiver.receiver_node:main',
        ],
    },
)
