#!/usr/bin/env python

from distutils.core import setup
from catkin_pkg.python_setup import generate_distutils_setup

d = generate_distutils_setup(
   packages=['mdr_simple_grasp_planner'],
   package_dir={'mdr_simple_grasp_planner': 'ros/src/mdr_simple_grasp_planner'}
)

setup(**d)
