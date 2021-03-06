#!/usr/bin/env python
# Importing the required libraries
from plutodrone.msg import *
from geometry_msgs.msg import PoseArray
from geometry_msgs.msg import Pose
from std_msgs.msg import Int16
from std_msgs.msg import Int64
from std_msgs.msg import Float64
from std_msgs.msg import String
from aruco_msgs.msg import MarkerArray
from pid_tune.msg import PidTune
import rospy
import time

class PID():
    def __init__(self):
        rospy.init_node('PID')

        # ================== INITIALISE ========================#
        self.cmd = PlutoMsg()
        self.pid_sample_time = 0.10 #in sec #how frequently should pid run #NOTE: stimulation step time is 0.050 sec
        self.zero_line_value = 0.0
        # [x,y,z,yaw_value]
        self.droneAruco_pos = [0.0,0.0,0.0,0.0]	
        self.initialSetPoint = [5.68, -1.91, 33.40, 0.0]
        self.start = [5.61, -1.89, 54.95, 0.0]
        self.setPoint = PoseArray()

        #[pitch, roll, throttle, yaw]
        self.output = [0.0, 0.0, 0.0, 0.0]
        self.prev_values = [0,0,0,0]
        self.max_values = [1700,1700,1800,1800]
        self.min_values = [1300,1300,1200,1200]
        self.Kp = [0.006*1015,214*0.06,203*0.06,0.006*310]#[5.13, 12, 23.1, 9]
        self.Ki = [0.008*0,43*0.008,0.0,0.0008*96]#[0.8 , 0, 0, 0.1496]
        self.Kd = [0.003*0,118*0.0375,1795*0.3,0.03*2100]#[13.365, 58.5, 342.9, 112.83]

        self.proposnal = [0.0, 0.0, 0.0, 0.0]
        self.iterm = [0.0, 0.0, 0.0, 0.0]
        # self.sum_of_error = [0.0, 0.0, 0.0, 0.0]
        self.differential = [0.0, 0.0, 0.0, 0.0]

        # ============================ Publisher =========================#
        self.drone_command_pub = rospy.Publisher('/drone_command', PlutoMsg, queue_size=5)
        self.error_pub = [None,None,None,None] #list of publiser - simlpy initialised
        self.error_pub[0] = rospy.Publisher('/pitch_error', Float64, queue_size=1)
        self.error_pub[1] = rospy.Publisher('/roll_error', Float64, queue_size=1)
        self.error_pub[2] = rospy.Publisher('/alt_error', Float64, queue_size=1)
        self.error_pub[3] = rospy.Publisher('/yaw_error', Float64, queue_size=1)
        self.zero_line_pub = rospy.Publisher('/zero_line', Float64, queue_size=1)
        self.next = rospy.Publisher('/next_command', String, queue_size = 100)

        # ========================= Subscriber ======================#
        rospy.Subscriber('whycon/poses', PoseArray, self.whycon_cb)
        rospy.Subscriber('/drone_yaw',Float64, self.droneYaw_cb)
        rospy.Subscriber('/vrep/waypoints', PoseArray, self.setWayPoint)

        #ARMING THE DRONE
        self.arm()

    def pid(self,goalPoints):
        self.proposnal = [0.0, 0.0, 0.0, 0.0] #reset to 0
        self.differential = [0.0, 0.0, 0.0, 0.0] #reset to 0
        for i in range (0, 4):
            self.proposnal[i] = goalPoints[i] - self.droneAruco_pos[i]
            # self.sum_of_error[i] = self.sum_of_error[i] + self.proposnal[i]
            self.iterm[i] = self.Ki[i]*(self.iterm[i] + self.proposnal[i])
            self.differential[i] = self.proposnal[i] - self.prev_values[i]
            self.output[i] = (self.Kp[i] * self.proposnal[i]) + self.iterm[i] + (self.Kd[i] * self.differential[i])
            self.prev_values[i] = self.proposnal[i]

            self.error_pub[i].publish(self.proposnal[i])

        self.cmd.rcPitch = 		1500 - self.output[0] #(+ve) want to decre.
        self.cmd.rcRoll = 		1500 - self.output[1] #(-ve) want to incre.
        self.cmd.rcThrottle = 	1500 - self.output[2] #(-ve) want to incre.
        self.cmd.rcYaw = 		1500 + self.output[3]

        self.limit()

        self.drone_command_pub.publish(self.cmd)
        self.zero_line_pub.publish(self.zero_line_value)

        rospy.sleep(self.pid_sample_time)
        return self.proposnal

    def disarm(self):
        self.cmd.rcAUX4 = 1100
        self.drone_command_pub.publish(self.cmd)
        rospy.sleep(1)

    def arm(self):
        self.disarm() #always disarm before arming
        self.cmd.rcRoll = 1500
        self.cmd.rcYaw = 1500
        self.cmd.rcPitch = 1500
        self.cmd.rcThrottle = 1000 # <------
        self.cmd.rcAUX1 = 1500 
        self.cmd.rcAUX2 = 1500
        self.cmd.rcAUX3 = 1500
        self.cmd.rcAUX4 = 1500
        self.cmd.plutoIndex = 0
        self.drone_command_pub.publish(self.cmd)
        rospy.sleep(1)
    def whycon_cb(self,msg):
        self.droneAruco_pos[0] = msg.poses[0].position.x
        self.droneAruco_pos[1] = msg.poses[0].position.y
        self.droneAruco_pos[2] = msg.poses[0].position.z
    def droneYaw_cb(self, yw):
        self.droneAruco_pos[3] = yw.data
    
    def limit(self):
        for i in range (0, 4):
            if self.output[i] > self.max_values[i] :
                self.output[i] = self.max_values[i]
            elif self.output[i] < self.min_values[i] :
                self.output[i] = self.min_values[i]
        if self.cmd.rcPitch > self.max_values[0]:
             self.cmd.rcPitch = self.max_values[0]
        elif self.cmd.rcPitch < self.min_values[0]:
             self.cmd.rcPitch = self.min_values[0]
        if self.cmd.rcRoll > self.max_values[1]:
             self.cmd.rcRoll = self.max_values[1]
        elif self.cmd.rcRoll < self.min_values[1]:
             self.cmd.rcRoll = self.min_values[1]
        if self.cmd.rcThrottle > self.max_values[2]:
             self.cmd.rcThrottle = self.max_values[2]
        elif self.cmd.rcThrottle < self.min_values[2]:
             self.cmd.rcThrottle = self.min_values[2]
        if self.cmd.rcYaw > self.max_values[3]:
             self.cmd.rcYaw = self.max_values[3]
        elif self.cmd.rcYaw < self.min_values[3]:
             self.cmd.rcYaw = self.min_values[3]
    
    def setWayPoint(self, msg):
        self.setPoint.poses = msg.poses

if __name__ == '__main__':
    pid_class = PID()
    error = []
    while True:
        error = pid_class.pid(pid_class.initialSetPoint)
        if (abs(error[0]) <= 0.5 and abs(error[1]) <= 0.5 and abs(error[2]) <= 0.5):
            break
    for i in range (0, 3):
        if i != 0:
            print("next_target")
        pid_class.next.publish('1')
        rospy.sleep(0.5)
        length = len(pid_class.setPoint.poses)
        for j in range (0, length):
            temp = [0.0, 0.0, 0.0, 0.0]
            temp[0] = pid_class.setPoint.poses[j].position.x
            temp[1] = pid_class.setPoint.poses[j].position.y
            temp[2] = pid_class.setPoint.poses[j].position.z
            temp[3] = 0.0
            while (True):
                error = pid_class.pid(temp)
                if (error[0] <= 0.5 and error[1] <= 0.5 and error[2] <= 0.5):
                    break
    # pid_class.disarm()

    #land at start point
    while True:
        error = pid_class.pid(pid_class.start)
        if (abs(error[0]) <= 0.5 and abs(error[1]) <= 0.5 and abs(error[2]) <= 1):
            pid_class.disarm()
            break