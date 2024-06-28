"""

EKF implementation for UWB localization

--- 작성일 :2024.05.05 송인용 ---

기존에 테스트용으로 사용한 버전과 추가로 센서 데이터 결합 버전 모음

"""



import numpy as np

np.set_printoptions(precision=3,suppress=True)



class EKF_ver2() :
    def __init__(self):

        self.A_k_minus_1 = np.array([[1.0, 0, 0, 0, 0],
                        [  0, 1.0, 0, 0, 0],
                        [ 0, 0, 1.0, 0, 0],
                        [ 0, 0, 0, 1.0, 0],
                        [ 0, 0, 0, 0, 1.0]])
        # Noise applied to the forward kinematics
        self.process_noise_v_k_minus_1 = np.array([0.01,0.01,0.003, 0.001,0.001])

        # State model noise covariance matrix Q_k
        self.Q_k = np.array([[0.01, 0, 0, 0, 0],
                        [  0, 0.01, 0, 0, 0],
                        [ 0, 0, 0.01, 0, 0],
                        [ 0, 0, 0, 0.01, 0],
                        [ 0, 0, 0, 0, 0.01]])
        # Measurement matrix H_k
        self.H_k = np.array([[1.0, 0, 0, 0, 0],
                        [  0,1.0, 0, 0, 0],
                        [  0, 0, 1.0, 0, 0],
                        [  0, 0, 0, 1.0, 0],
                        [  0, 0, 0, 0, 1.0]])
        # Sensor measurement noise covariance matrix R_k
        self.R_k = np.array([[0.01, 0, 0, 0, 0],
                        [  0, 0.01, 0, 0, 0],
                        [ 0, 0, 0.01, 0, 0],
                        [ 0, 0, 0, 0.001, 0],
                        [ 0, 0, 0, 0, 0.001]])
        # Sensor noise.
        self.sensor_noise_w_k = np.array([0.01,0.01,0.001, 0.001,0.001])


    def getB(self, yaw, vx, vy, deltak):
        B = np.zeros((5, 3))  # 5 states and 2 control inputs
        # Position change influenced by current velocity
        #B[0, 0] = vx * deltak + 0.5 * ax * (deltak**2) * np.cos(yaw)  # x position change due to vx and ax
        # Yaw influence

        B[0, 2] = deltak # Direct influence of yaw on itself
        B[3, 0] = vx * deltak # Direct influence of distance_x on itself
        B[4, 1] = vy * deltak # Direct influence of distance_y on itself

        
        # Velocity influences
        B[1, 0] = np.cos(yaw) * deltak  # yaw_rate effect on x position
        B[2, 1] = np.sin(yaw) * deltak  # yaw_rate effect on y position
        
        B[1, 1] = -np.sin(yaw) * deltak  # yaw_rate effect on x position
        B[2, 0] = -np.cos(yaw) * deltak   # yaw_rate effect on y position


        return B

    def ekf(self, z_k_observation_vector, state_estimate_k_minus_1, 
        control_vector_k_minus_1, P_k_minus_1, dk):
        
    ######################### Predict #############################
    # Predict the state estimate at time k based on the state 
    # estimate at time k-1 and the control input applied at time k-1.
        state_estimate_k = self.A_k_minus_1 @ (
                state_estimate_k_minus_1) + (
                self.getB(state_estimate_k_minus_1[0], state_estimate_k_minus_1[3], state_estimate_k_minus_1[4], dk)) @ (
                control_vector_k_minus_1) + (
                self.process_noise_v_k_minus_1)
                
        #print(f'State Estimate Before EKF={state_estimate_k}')

          
        # Predict the state covariance estimate based on the previous
        # covariance and some noise
        P_k = self.A_k_minus_1 @ P_k_minus_1 @ self.A_k_minus_1.T + (
                self.Q_k)
        ################### Update (Correct) ##########################
        # Calculate the difference between the actual sensor measurements
        # at time k minus what the measurement model predicted 
        # the sensor measurements would be for the current timestep k.
        measurement_residual_y_k = z_k_observation_vector - (
                (self.H_k @ state_estimate_k) + (
                self.sensor_noise_w_k))
        
                # Calculate the measurement residual covariance
        S_k = self.H_k @ P_k @ self.H_k.T + self.R_k
            
        # Calculate the near-optimal Kalman gain
        # We use pseudoinverse since some of the matrices might be
        # non-square or singular.
        K_k = P_k @ self.H_k.T @ np.linalg.pinv(S_k)
            
        # Calculate an updated state estimate for time k
        state_estimate_k = state_estimate_k + (K_k @ measurement_residual_y_k)
        
        # Update the state covariance estimate for time k
        P_k = P_k - (K_k @ self.H_k @ P_k)
        
        # Print the best (near-optimal) estimate of the current state of the robot
        #print(f'State Estimate After EKF={state_estimate_k}')
    
        # Return the updated state and covariance estimates
        return state_estimate_k, P_k, z_k_observation_vector



class EKF_ver1() :
    def __init__(self):

        self.A_k_minus_1 = np.array([[1.0, 0, 0, 0, 0],
                        [  0, 1.0, 0, 0, 0],
                        [ 0, 0, 1.0, 0, 0],
                        [ 0, 0, 0, 1.0, 0],
                        [ 0, 0, 0, 0, 1.0]])
        # Noise applied to the forward kinematics
        self.process_noise_v_k_minus_1 = np.array([0.01,0.01,0.003, 0.01,0.01])

        # State model noise covariance matrix Q_k
        self.Q_k = np.array([[0.01, 0, 0, 0, 0],
                        [  0, 0.01, 0, 0, 0],
                        [ 0, 0, 0.01, 0, 0],
                        [ 0, 0, 0, 0.01, 0],
                        [ 0, 0, 0, 0, 0.01]])
        # Measurement matrix H_k
        self.H_k = np.array([[1.0, 0, 0, 0, 0],
                        [  0,1.0, 0, 0, 0],
                        [  0, 0, 1.0, 0, 0],
                        [  0, 0, 0, 1.0, 0],
                        [  0, 0, 0, 0, 1.0]])
        # Sensor measurement noise covariance matrix R_k
        self.R_k = np.array([[0.01, 0, 0, 0, 0],
                        [  0, 0.01, 0, 0, 0],
                        [ 0, 0, 0.01, 0, 0],
                        [ 0, 0, 0, 0.01, 0],
                        [ 0, 0, 0, 0, 0.01]])
        # Sensor noise.
        self.sensor_noise_w_k = np.array([0.01,0.01,0.001, 0.01,0.01])


    def getB(self, yaw, vx, vy, deltak):
        B = np.zeros((5, 2))  # 5 states and 2 control inputs
        # Position change influenced by current velocity
        #B[0, 0] = vx * deltak + 0.5 * ax * (deltak**2) * np.cos(yaw)  # x position change due to vx and ax
        B[0, 1] = deltak
        B[1, 0] = np.cos(yaw)*deltak 
        #B[1, 0] = vy * deltak + 0.5 * ay * (deltak**2) * np.sin(yaw) 
        # Yaw rate influence directly on yaw
        B[2, 0] = np.sin(yaw)*deltak  # yaw_rate * deltak for direct influence on yaw
        # Acceleration influences on velocities
        B[3, 0] = deltak
        B[4, 0] = deltak
        return B

    def ekf(self, z_k_observation_vector, state_estimate_k_minus_1, 
        control_vector_k_minus_1, P_k_minus_1, dk):
        
    ######################### Predict #############################
    # Predict the state estimate at time k based on the state 
    # estimate at time k-1 and the control input applied at time k-1.
        state_estimate_k = self.A_k_minus_1 @ (
                state_estimate_k_minus_1) + (
                self.getB(state_estimate_k_minus_1[0], state_estimate_k_minus_1[3], state_estimate_k_minus_1[4], dk)) @ (
                control_vector_k_minus_1) + (
                self.process_noise_v_k_minus_1)
                
        #print(f'State Estimate Before EKF={state_estimate_k}')

          
        # Predict the state covariance estimate based on the previous
        # covariance and some noise
        P_k = self.A_k_minus_1 @ P_k_minus_1 @ self.A_k_minus_1.T + (
                self.Q_k)
        ################### Update (Correct) ##########################
        # Calculate the difference between the actual sensor measurements
        # at time k minus what the measurement model predicted 
        # the sensor measurements would be for the current timestep k.
        measurement_residual_y_k = z_k_observation_vector - (
                (self.H_k @ state_estimate_k) + (
                self.sensor_noise_w_k))
        
                # Calculate the measurement residual covariance
        S_k = self.H_k @ P_k @ self.H_k.T + self.R_k
            
        # Calculate the near-optimal Kalman gain
        # We use pseudoinverse since some of the matrices might be
        # non-square or singular.
        K_k = P_k @ self.H_k.T @ np.linalg.pinv(S_k)
            
        # Calculate an updated state estimate for time k
        state_estimate_k = state_estimate_k + (K_k @ measurement_residual_y_k)
        
        # Update the state covariance estimate for time k
        P_k = P_k - (K_k @ self.H_k @ P_k)
        
        # Print the best (near-optimal) estimate of the current state of the robot
        #print(f'State Estimate After EKF={state_estimate_k}')
    
        # Return the updated state and covariance estimates
        return state_estimate_k, P_k, z_k_observation_vector




"""
UWB 좌표와 Yaw 축 결합하는 처음 테스트용 EKF 함수
https://automaticaddison.com/extended-kalman-filter-ekf-with-python-code-example/

""" 
class EKF_basic() :
    def __init__(self):
# Supress scientific notation when printing NumPy arrays
        
        
        # A matrix
        # 3x3 matrix -> number of states x number of states matrix
        # Expresses how the state of the system [x,y,yaw] changes 
        # from k-1 to k when no control command is executed.
        # Typically a robot on wheels only drives when the wheels are told to turn.
        # For this case, A is the identity matrix.
        # A is sometimes F in the literature.
        self.A_k_minus_1 = np.array([[1.0,  0,   0],
                                [  0,1.0,   0],
                                [  0,  0, 1.0]])
        
        # Noise applied to the forward kinematics (calculation
        # of the estimated state at time k from the state
        # transition model of the mobile robot). This is a vector
        # with the number of elements equal to the number of states
        self.process_noise_v_k_minus_1 = np.array([0.01,0.01,0.003])
            
        # State model noise covariance matrix Q_k
        # When Q is large, the Kalman Filter tracks large changes in 
        # the sensor measurements more closely than for smaller Q.
        # Q is a square matrix that has the same number of rows as states.
        self.Q_k = np.array([[0.01,   0,   0],
                        [  0, 0.01,   0],
                        [  0,   0, 0.01]])
    

            # Measurement matrix H_k
        # Used to convert the predicted state estimate at time k
        # into predicted sensor measurements at time k.
        # In this case, H will be the identity matrix since the 
        # estimated state maps directly to state measurements from the 
        # odometry data [x, y, yaw]
        # H has the same number of rows as sensor measurements
        # and same number of columns as states.
        self.H_k = np.array([[1.0,  0,   0],
                        [  0,1.0,   0],
                        [  0,  0, 1.0]])
                                
        # Sensor measurement noise covariance matrix R_k
        # Has the same number of rows and columns as sensor measurements.
        # If we are sure about the measurements, R will be near zero.
        self.R_k = np.array([[0.01,   0,    0],
                        [  0, 0.01,    0],
                        [  0,    0, 0.01]])  
                        
        # Sensor noise. This is a vector with the
        # number of elements equal to the number of sensor measurements.
        self.sensor_noise_w_k = np.array([0.02,0.02,0.01])


    def getB(self, yaw, deltak):
        """
        Calculates and returns the B matrix
        3x2 matix -> number of states x number of control inputs
        The control inputs are the forward speed and the
        rotation rate around the z axis from the x-axis in the 
        counterclockwise direction.
        [v,yaw_rate]
        Expresses how the state of the system [x,y,yaw] changes
        from k-1 to k due to the control commands (i.e. control input).
        :param yaw: The yaw angle (rotation angle around the z axis) in rad 
        :param deltak: The change in time from time step k-1 to k in sec
        """
        B = np.array([  [np.cos(yaw)*deltak, 0],
                        [np.sin(yaw)*deltak, 0],
                        [0, deltak]])
        return B
    
    def ekf(self, z_k_observation_vector, state_estimate_k_minus_1, 
        control_vector_k_minus_1, P_k_minus_1, dk):

    ######################### Predict #############################
    # Predict the state estimate at time k based on the state 
    # estimate at time k-1 and the control input applied at time k-1.
        state_estimate_k = self.A_k_minus_1 @ (
                state_estimate_k_minus_1) + (
                self.getB(state_estimate_k_minus_1[0],dk)) @ (
                control_vector_k_minus_1) + (
                self.process_noise_v_k_minus_1)
                
        #print(f'State Estimate Before EKF={state_estimate_k}')
                
        # Predict the state covariance estimate based on the previous
        # covariance and some noise
        P_k = self.A_k_minus_1 @ P_k_minus_1 @ self.A_k_minus_1.T + (
                self.Q_k)
            
        ################### Update (Correct) ##########################
        # Calculate the difference between the actual sensor measurements
        # at time k minus what the measurement model predicted 
        # the sensor measurements would be for the current timestep k.
        measurement_residual_y_k = z_k_observation_vector - (
                (self.H_k @ state_estimate_k) + (
                self.sensor_noise_w_k))
        
                # Calculate the measurement residual covariance
        S_k = self.H_k @ P_k @ self.H_k.T + self.R_k
            
        # Calculate the near-optimal Kalman gain
        # We use pseudoinverse since some of the matrices might be
        # non-square or singular.
        K_k = P_k @ self.H_k.T @ np.linalg.pinv(S_k)
            
        # Calculate an updated state estimate for time k
        state_estimate_k = state_estimate_k + (K_k @ measurement_residual_y_k)
        
        # Update the state covariance estimate for time k
        P_k = P_k - (K_k @ self.H_k @ P_k)
        
        # Print the best (near-optimal) estimate of the current state of the robot
        #print(f'State Estimate After EKF={state_estimate_k}')
    
        # Return the updated state and covariance estimates
        return state_estimate_k, P_k, z_k_observation_vector