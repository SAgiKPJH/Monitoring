import os
from glob import glob

from setuptools import setup

package_name = "baby_monitor"

setup(
    name=package_name,
    version="0.1.0",
    packages=[package_name],
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        (os.path.join("share", package_name, "launch"), glob("launch/*.launch.py")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="juhyung",
    maintainer_email="juhyung1021@gmail.com",
    description="Baby monitor (15_rdk_x5_runtime/monitoring.py) as a ROS2 node — alarm/status topics.",
    license="MIT",
    entry_points={
        "console_scripts": [
            "monitor_node = baby_monitor.monitor_node:main",
        ],
    },
)
