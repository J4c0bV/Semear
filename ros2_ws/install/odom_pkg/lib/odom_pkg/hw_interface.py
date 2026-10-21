#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist, TransformStamped
from nav_msgs.msg import Odometry
from std_msgs.msg import String
from sensor_msgs.msg import JointState
from tf2_ros import TransformBroadcaster
import math

class HWInterface(Node):
    def __init__(self):
        super().__init__('hw_interface_node')
        self.cmd_vel_sub = self.create_subscription(Twist, 'cmd_vel', self.cb_cmd_vel, 10)
        self.joint_state_sub = self.create_subscription(JointState, 'joint_states', self.cb_joint_states, 10)
    
        self.odom_pub = self.create_publisher(Odometry, "odom", 50)
        self.tf_broadcaster = TransformBroadcaster(self)

        self.raio_roda = 0.05     
        self.largura_roda = 0.22
        self.max_velocidade = 2.0  
        self.min_velocidade = 0

        self.odom_x = 0.0
        self.odom_y = 0.0
        self.odom_yaw = 0.0
    
        self.tempo_anterior = self.get_clock().now()

        self.velocidade_linear_atual = 0.0
        self.velocidade_angular_atual = 0.0

        self.watchdog_timer = self.create_timer(0.2, self.cb_cmd_timeout)

    def cb_cmd_vel(self, msg):
        pass 

    def cb_joint_states(self, msg):
        try:
            idx_left = next(i for i, name in enumerate(msg.name) if 'left_wheel_joint' in name)
            idx_right = next(i for i, name in enumerate(msg.name) if 'right_wheel_joint' in name)
            
            omega_left = msg.velocity[idx_left]
            omega_right = msg.velocity[idx_right]
            
            v_left_ms = omega_left * self.raio_roda
            v_right_ms = omega_right * self.raio_roda

            self.velocidade_linear_atual = (v_right_ms + v_left_ms) / 2.0
            self.velocidade_angular_atual = (v_right_ms - v_left_ms) / self.largura_roda
            
            # FILTRO REFORÇADO: Bloqueia saltos de velocidade Linear E Angular usando abs()
            if abs(self.velocidade_linear_atual) >= self.max_velocidade:
                self.velocidade_linear_atual = 0.0
                
            if abs(self.velocidade_angular_atual) >= 5.0: # Limite de segurança para não corromper o Yaw
                self.velocidade_angular_atual = 0.0

            self.update_odometry()
        except StopIteration:
            pass

    def update_odometry(self):
        tempo_agora = self.get_clock().now()
        dt = (tempo_agora - self.tempo_anterior).nanoseconds / 1e9
        self.tempo_anterior = tempo_agora

        # NOVA PROTEÇÃO: O abs() impede que saltos de tempo NEGATIVOS destruam a odometria
        if abs(dt) > 0.5:
            dt = 0.0
            
        delta_x = self.velocidade_linear_atual * math.cos(self.odom_yaw) * dt
        delta_y = self.velocidade_linear_atual * math.sin(self.odom_yaw) * dt
        delta_yaw = self.velocidade_angular_atual * dt

        self.odom_x += delta_x
        self.odom_y += delta_y
        self.odom_yaw += delta_yaw

        q_z = math.sin(self.odom_yaw / 2.0)
        q_w = math.cos(self.odom_yaw / 2.0)

        t = TransformStamped()
        t.header.stamp = tempo_agora.to_msg()
        t.header.frame_id = 'odom'
        t.child_frame_id = 'base_link'
        t.transform.translation.x = self.odom_x
        t.transform.translation.y = self.odom_y
        t.transform.rotation.z = q_z
        t.transform.rotation.w = q_w
        self.tf_broadcaster.sendTransform(t)

        odom = Odometry()
        odom.header.stamp = tempo_agora.to_msg()
        odom.header.frame_id = 'odom'
        odom.child_frame_id = 'base_link'
        odom.pose.pose.position.x = self.odom_x
        odom.pose.pose.position.y = self.odom_y
        odom.pose.pose.orientation.z = q_z
        odom.pose.pose.orientation.w = q_w
        odom.twist.twist.linear.x = self.velocidade_linear_atual
        odom.twist.twist.angular.z = self.velocidade_angular_atual
        self.odom_pub.publish(odom)

    def cb_cmd_timeout(self):
        pass

def main(args=None):
    rclpy.init(args=args)
    interface = HWInterface()
    rclpy.spin(interface)
    interface.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()