cmake_minimum_required(VERSION 2.8.3)
project(mdr_gripper_controller)

find_package(catkin REQUIRED
  COMPONENTS
    roslint
    rospy
)

catkin_python_setup()
roslint_python()

catkin_package(
  CATKIN_DEPENDS
    std_msgs
)

if(CATKIN_ENABLE_TESTING)
  find_package(roslaunch REQUIRED)
  roslaunch_add_file_check(ros/launch)
endif()

install(PROGRAMS
  ros/scripts/gripper_controller
  DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION}
)
