#!/bin/bash
#please clonse this in colcon_ws on jetson
source /opt/ros/humble/setup.bash
cd ~/colcon_ws
colcon build
source install/setup.bash
sudo cp ~/colcon_ws/src/ros2_jetson_stats/ros2_jtop.service /etc/systemd/system/ros2_jtop.service
sudo systemctl enable ros2_jtop.service
sudo systemctl daemon_reload
sudo systemctl start ros2_jtop.service
