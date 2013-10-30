#!/usr/bin/python

######################### IMPORTS #########################

import roslib
roslib.load_manifest('mdr_common_states')
import rospy
import smach
import smach_ros

from simple_script_server import *
sss = simple_script_server()

import std_msgs.msg
import std_srvs.srv
import actionlib_msgs.msg
import moveit_msgs.msg

#import mdr_manipulation_msgs.msg

from mdr_common_states.common_states_speech import *


class init_guiding(smach.State):
	def __init__(self):
		smach.State.__init__(self, outcomes=['success', 'failed'])

	def execute(self, userdata):
		# command the operator
		SAY("Please wait a moment")
		sss.move("arm","pregrasp", True)
		
		guiding_client = rospy.ServiceProxy('/mcr_behaviors/haptic/start', std_srvs.srv.Empty)
		rospy.wait_for_service('/mcr_behaviors/haptic/start', 3)
		try:
			guiding_client()
			SAY("You can guide me now!")
			return 'success'
		except rospy.ServiceException, e:
			print "Service call failed: %s"%e
			return 'failed'

class stop_guiding(smach.State):
	def __init__(self):
		smach.State.__init__(self, outcomes=['success','failed'])
	
	def execute(self,userdata):
		guiding_client_pause = rospy.ServiceProxy('/mcr_behaviors/haptic/stop', std_srvs.srv.Empty)
		rospy.wait_for_service('/mcr_behaviors/haptic/stop', 3)
		
		try:
			guiding_client_pause()
			SAY("Thank you!")
			result = "success"
		except:
			print "Service call failed: %s"%e
			result = 'failed'
		
		sss.move("arm", "folded")
		return result
		
class point_to_object(smach.State):
	def __init__(self):
		smach.State.__init__(self, outcomes=['success','failed'], input_keys=['grasp_position'])
	
	def execute(self, userdata):
		sss.move("torso","home")
		req = mdr_manipulation_msgs.srv.PointToLocationRequest()
		req.location.header.frame_id = "/base_link"
		req.location.point = userdata.grasp_position
				
		print "Now waiting for service"
		rospy.wait_for_service('/mdr_manipulation/point_to_location')
		pointing = rospy.ServiceProxy('/mdr_manipulation/point_to_location', mdr_manipulation_msgs.srv.PointToLocation)
		try:
			resp = pointing(req)
		except rospy.ServiceException, e:
			print "Service did not process request: %s"%str(e)
		
		if (resp.success):
			SAY("There is the object")
			result = 'success'
		else:
			SAY("Sorry, I could not point at the object")
			result = 'failed'
		
		rospy.sleep(5)
		sss.move("arm", "folded")
		
		return result



class clean_table(smach.State):
	def __init__(self):
		smach.State.__init__(self, outcomes=['success','failed'], input_keys=['grasp_position'])
	
	def execute(self, userdata):
		sss.move("torso","home")
		sss.move("sdh","fist")

		req = mdr_manipulation_msgs.srv.CleanTableRequest()
		req = mdr_manipulation_msgs.srv.CleanTableRequest()
		
		req.area.type = arm_navigation_msgs.msg.Shape.BOX
		req.area.dimensions.append(0.2)
		req.area.dimensions.append(0.2)
		
		req.sponge_position.header.frame_id = "/base_link"
		req.sponge_position.header.stamp = rospy.Time.now() - rospy.Duration(0.5)
		req.sponge_position.point = userdata.grasp_position
		req.sponge_position.point.x -= 0.05
		req.sponge_position.point.y += 0.03
		hand = 0.2
		if rospy.has_param('/table_hight'):
			req.sponge_position.point.z = rospy.get_param('/table_hight') + 0.04
		else:
			req.sponge_position.point.z += 0.07
		req.sponge_position.point.z += hand
		
		req.area_center.header.frame_id = "/base_link"
		req.area_center.header.stamp = rospy.Time.now() - rospy.Duration(0.5)
		req.area_center.point.x = -0.6
		req.area_center.point.y =  0.0
		req.area_center.point.z =  req.sponge_position.point.z
				
		print "Now waiting for service: /mcr_manipulation/clean_table"
		rospy.wait_for_service('/mcr_manipulation/clean_table')
		clean = rospy.ServiceProxy('/mcr_manipulation/clean_table', mdr_manipulation_msgs.srv.CleanTable)
		try:
			resp = clean(req)
			if (resp.success):
				SAY("The table is clean now")
				result = 'success'
			else:
				SAY("Sorry, I could not clean the table")
				result = 'failed'
		except rospy.ServiceException, e:
			print "Service did not process request: %s"%str(e)
			result = 'failed'
		
		sss.move("arm", "clean_table")
		sss.move("arm", "look_at_table")
		sss.move("arm", "look_at_table-to-folded")
		return result

		
			
class grasp_object(smach.State):
	def __init__(self):
		smach.State.__init__(self, outcomes=['success','failed','retry'], input_keys=['grasp_position'])
		self.grasp_object_srv = rospy.ServiceProxy('grasp', mdr_manipulation_msgs.srv.Grasp)
		self.set_joint_stiffness = rospy.ServiceProxy('/arm_controller/set_joint_stiffness', SetJointStiffness)
		self.retry_count = 0
	
	def execute(self, userdata):
		sss.move("torso","home")
		rospy.wait_for_service('/arm_controller/set_joint_stiffness', 5)
		try:
			req = SetJointStiffnessRequest()
			req.joint_stiffness = [150,150,150,150,150,150,150]
			self.set_joint_stiffness(req)
		except rospy.ServiceException,e:
			print "Service call failed: %s"%e
			return 'failed'

		grasp = mdr_manipulation_msgs.srv.GraspRequest()
		grasp.position.header.frame_id = "/base_link"
		grasp.position.point = userdata.grasp_position
		#try to get table hight
	#	if rospy.has_param('/table_hight'):
	#		grasp.position.point.z = rospy.get_param('/table_hight') + 0.11
				
		print "Now waiting for service"
		rospy.wait_for_service('/mcr_manipulation/pick')
		picking = rospy.ServiceProxy('/mcr_manipulation/pick', mdr_manipulation_msgs.srv.Grasp)
		try:
			resp = picking(grasp)
		except rospy.ServiceException, e:
			print "Service did not process request: %s"%str(e)
		
		if (resp.result == 0):
			#SAY("I grasp the object successfully!")
			self.retry_count = 0

			#sss.move("arm", "pregrasp")
			
			self.retry_count = 0
			return 'success'
		else:
			if (self.retry_count > 3):
				SAY("I give up grasping the object")
				sss.move("torso","home")
				sss.move("arm", "look_at_table-to-folded")
				return 'failed'
			SAY("I could not grasp the object, but I will try again.")
			self.retry_count = self.retry_count + 1
			return 'retry'

class hand_over_object(smach.State):
	def __init__(self):
		smach.State.__init__(self, outcomes=['success', 'failed'])
	
	def execute(self, userdata):
		sss.move("head","front_face",False)
		handle_arm = sss.move("arm",["intermediateback", "intermediatefront","brsu_overtray"],False)

		handle_tray = sss.move("tray","up",False)
		handle_tray.wait()

		handle_arm.wait()
		sss.move("arm","tray_front")

		sss.move("sdh","cylopen")
		handle_arm = sss.move("arm","tray-to-folded",False)

		sss.sleep(2)
		sss.move("sdh","cylclosed")
		handle_arm.wait()
		
		handle_torso = sss.move("torso","nod",False)		
	
		SAY("Please take the object from my tray!")
		handle_torso.wait()
		sss.sleep(2)
		sss.move("tray","down")
		return 'success'


class put_object_in_hand(smach.State):
	def __init__(self):
		smach.State.__init__(self, outcomes=['success','failed'])
		self.get_close_request = rospy.ServiceProxy('/sdh_controller/one_pad_contact', Trigger)
		self.get_force_request = rospy.ServiceProxy('/is_external_force_applied', Trigger)
		self.memorize_current_force = rospy.ServiceProxy('/memorize_current_force', std_srvs.srv.Empty)
		self.get_bottle_state = rospy.ServiceProxy('/get_bottle_state', BottleState)
		self.set_joint_stiffness = rospy.ServiceProxy('/arm_controller/set_joint_stiffness', SetJointStiffness)
		self.set_operation_mode = rospy.ServiceProxy('/arm_controller/set_operation_mode', SetOperationMode)
		self.pub_arm_vel = rospy.Publisher('/arm_controller/command', JointTrajectory)

	def execute(self, userdata):

		sss.move("head","back",False)
		sss.move("arm","pregrasp")
			
		#  set arm to stiffness mode
		rospy.wait_for_service('/arm_controller/set_joint_stiffness', 5)
		try:
			req = SetJointStiffnessRequest()
			req.joint_stiffness = [200,200,200,200,200,200,200]
			self.set_joint_stiffness(req)
		except rospy.ServiceException,e:
			print "Service call failed: %s"%e
			return 'failed'
			
		sss.move("arm","pregrasp")
	
		handle_sdh = sss.move("sdh","cylopen",False)
		SAY("Please press a bottle into my hand")
		handle_sdh.wait()
		
		rospy.wait_for_service('/memorize_current_force', 5)
		try:
			self.memorize_current_force()
			rospy.sleep(0.1)
		except rospy.ServiceException,e:
			print "Service call failed: %s"%e
			return 'failed'
			
		close_request = False
		while not close_request:
			# check for tactile sensors
			rospy.wait_for_service('/sdh_controller/one_pad_contact', 5)
			try:
				close_request = self.get_close_request().success.data
			except rospy.ServiceException,e:
				print "Service call failed: %s"%e
				return 'failed'
			
			
			rospy.wait_for_service('/is_external_force_applied', 5)
			try:
				close_request = self.get_force_request().success.data
			except rospy.ServiceException,e:
				print "Service call failed: %s"%e
				return 'failed'
			if close_request: 
				print "grasp the object now"
			
			rospy.loginfo("waiting for bottle to be placed in hand")
			rospy.sleep(0.1)
		
		# close hand
		handle_sdh = sss.move("sdh","cylclosed",False)
		handle_torso = sss.move("torso","back",False)
		handle_torso.wait()
		sss.move("torso","home",False)
		handle_sdh.wait()
		
		# check if anything is in hand
		rospy.wait_for_service('/get_bottle_state', 5)
		try:
			bottle_state = self.get_bottle_state().state
		except rospy.ServiceException,e:
			print "Service call failed: %s"%e
			return 'failed'
		if bottle_state == 1:
			SAY("There is nothing in my hand.")
			sss.move("arm","folded")
			return 'failed'
		else:
			SAY("Please step aside.")
		rospy.sleep(3)
		return 'success'
		
		
class weight_bottle(smach.State):
	def __init__(self):
		smach.State.__init__(self, outcomes=['success','failed'],input_keys=['bottle_state','force_x_with_bottle'],output_keys=['bottle_state','force_x_with_bottle'])
		self.get_bottle_state = rospy.ServiceProxy('/get_bottle_state', BottleState)
		self.get_wrench = rospy.ServiceProxy('/get_wrench', GetWrench)

	def execute(self, userdata):
		#sss.move("arm","pregrasp")
		sss.sleep(1)
	
		# do the weighting
		rospy.wait_for_service('/get_bottle_state', 5)
		try:
			bottle_state = self.get_bottle_state().state
		except rospy.ServiceException,e:
			print "Service call failed: %s"%e
			return 'failed'
		
		# store x axis force
		#rospy.wait_for_service('/get_wrench', 5)
		#try:
		#	res = self.get_wrench()
		#except rospy.ServiceException,e:
		#	print "Service call failed: %s"%e
		#	return 'failed'
		#userdata.force_x_with_bottle = res.wrench.wrench.force.x
			
		if bottle_state == 1:
			SAY("There is nothing in my hand.")
			return 'success'
		elif bottle_state == 2:
			SAY("The bottle is empty.")
			userdata.bottle_state = "empty"
		elif bottle_state == 3:
			SAY("The bottle is half full.")
			userdata.bottle_state = "half_full"
		elif bottle_state == 4:
			SAY("The bottle is full.")
			userdata.bottle_state = "full"
		else: # this should never happen
			return 'failed'
		return 'success'		


class release_object(smach.State):
	def __init__(self):
		smach.State.__init__(self, outcomes=['success','failed'])
		self.get_release_request = rospy.ServiceProxy('/is_external_force_applied', Trigger)
		self.memorize_current_force = rospy.ServiceProxy('/memorize_current_force', std_srvs.srv.Empty)
		self.set_joint_stiffness = rospy.ServiceProxy('/arm_controller/set_joint_stiffness', SetJointStiffness)

	def execute(self, userdata):
		SAY("Please pull it out of my hand.")
		
		rospy.wait_for_service('/memorize_current_force', 5)
		try:
			self.memorize_current_force()
			rospy.sleep(0.1)
		except rospy.ServiceException,e:
			print "Service call failed: %s"%e
			return 'failed'
			
		# wait for releasing the bottle
		release_request = False
		while not release_request:
			rospy.wait_for_service('/is_external_force_applied', 5)
			try:
				release_request = self.get_release_request().success.data
			except rospy.ServiceException,e:
				print "Service call failed: %s"%e
				return 'failed'
			if release_request: 
				print "release object now"
			rospy.loginfo("waiting for release request")
			rospy.sleep(0.1)
				
			# check for z axis
			#rospy.wait_for_service('/get_wrench', 5)
			#try:
			#	res = self.get_wrench()
			#except rospy.ServiceException,e:
			#	print "Service call failed: %s"%e
			#	return 'failed'
			#if abs(res.wrench.wrench.force.z) > 10:
			#	print "release z axis"
			#	release_request = True
			
		
		handle_sdh = sss.move("sdh","cylopen",False)
		handle_torso = sss.move("torso","back",False)

		handle_torso.wait()
		sss.move("torso","home",False)
		handle_sdh.wait()
		
		#  set arm to stiffness mode
		rospy.wait_for_service('/arm_controller/set_joint_stiffness', 5)
		try:
			req = SetJointStiffnessRequest()
			req.joint_stiffness = [300,300,300,300,300,300,300]
			self.set_joint_stiffness(req)
		except rospy.ServiceException,e:
			print "Service call failed: %s"%e
			return 'failed'
		
		sss.move("sdh","cylclosed",False)
		sss.move("torso","home",False)
		sss.move("head","front_face",False)
		sss.move("arm","folded")
		return 'success'		


class place_object_on_tray(smach.State):
	def __init__(self, trayPosition = ''):
		smach.State.__init__(self, outcomes=['success', 'failed'],input_keys=['position_on_tray'])
		self.trayPosition = trayPosition
		
	def execute(self, userdata):
		if self.trayPosition == '' and userdata.position_on_tray == '':
			handle_arm = sss.move("arm",["brsu_intermediateback", "intermediatefront","brsu_overtray","tray"],False)
			handle_tray = sss.move("tray","up")
			handle_tray.wait()
			handle_arm.wait()
			
			sss.move("sdh","cylopen")
			handle_arm = sss.move("arm", ["overtray", "intermediatefront", "brsu_intermediateback", "folded"],False)
			
			rospy.sleep(2)
			sss.move("sdh","cylclosed")
			handle_arm.wait()
			return 'success'
		if userdata.position_on_tray != '':
			self.trayPosition = userdata.position_on_tray

		if self.trayPosition == 'TRAY_1':
			# LINKE
			handle_arm = sss.move("arm",["brsu_intermediateback", "intermediatefront","brsu_overtray","tray_left"],False)
			handle_tray = sss.move("tray","up",False)
			handle_tray.wait()
			handle_arm.wait()

			sss.move("sdh","cylopen")
			handle_arm = sss.move("arm", ["overtray", "intermediatefront", "brsu_intermediateback", "folded"],False)

			sss.sleep(2)
			sss.move("sdh","cylclosed")
			handle_arm.wait()
			return 'success'

		elif self.trayPosition == 'TRAY_2':
			# RECHTE
			handle_arm = sss.move("arm",["brsu_intermediateback", "intermediatefront","tray_right"],False)
			handle_tray = sss.move("tray","up",False)
			handle_tray.wait()
			handle_arm.wait()
			
			sss.move("sdh","cylopen")
			handle_arm = sss.move("arm", ["intermediatefront", "brsu_intermediateback", "folded"],False)

			sss.sleep(2)
			sss.move("sdh","cylclosed")
			handle_arm.wait()
			return 'success'
		else:
			# Should not happen
			return 'success'
	
	
class move_arm_to_folded(smach.State):
	def __init__(self):
		smach.State.__init__(self, outcomes=['success'])
		
	def execute(self, userdata):
		handle_arm = sss.move("arm","folded",False)
		handle_arm.wait()
		return 'success'