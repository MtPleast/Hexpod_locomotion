# -^- coding:utf-8 -^-
from actorcritic.config import *
if ENVIRONMENT=="VREP":
    import vrep
    N = 50
else:
    import toyrep as vrep
    N=5
import numpy as np
import math
import time
import copy
"""
可以调用的接口：three_step_delta(newpos_delta,side,peb)
                three_step(newpos,side)
            传入的参数都是一个3*3的tensor，一个side取0或1代表哪组腿。
            只是delta是原来腿的位置基础上的差值
            均是以body的位置作为坐标系确定的点
            ped 为None或者 three_step newpos的shape是 3,3的时候:
                机器人的姿态永远有两个约束，body的位置在足尖的中心点，六个腿没有扭动（角度的平均值是0）
            否则由输入控制
用于测试和使用的更高级接口: walk_a_step(length=0.6,deg=0):
                        turn_a_deg(deg):
辅助接口：
        print_steps()画出所有足尖相对身体的位置
"""

# N=75

def recover(n=N):
    Lz = np.zeros(n+1)
    init_position = np.zeros((6, 3))
    # time.sleep(3)
    for i in range(6):
        res, init_position[i] = vrep.simxGetObjectPosition(clientID, S1[i], BCS, vrep.simx_opmode_oneshot_wait)
    for i in range(1,n+1):
        Lz[i] = init_position[0][2] - i * 0.1/n

    for i in range(1,n+1):
        vrep.simxSynchronousTrigger(clientID)
        for j in range(0,6,2):
            vrep.simxSetObjectPosition(clientID, Tip_target[j], BCS, [init_position[j][0], init_position[j][1], Lz[i]],
                               vrep.simx_opmode_oneshot_wait)
    for i in range(1,n+1):
        vrep.simxSynchronousTrigger(clientID)
        for j in range(1,6,2):
            vrep.simxSetObjectPosition(clientID, Tip_target[j], BCS, [init_position[j][0], init_position[j][1], Lz[i]],
                               vrep.simx_opmode_oneshot_wait)

def ave_ang(angs):
    angs = np.array(angs)
    x = np.cos(angs)
    y = np.sin(angs)
    return math.atan2(np.sum(y),np.sum(x))
def turnVec(vec,deg):
    """
    Get the vector after turned the vec some degree
    """
    assert(vec.shape==(3,))
    return np.array([
        vec[0]*np.cos(deg) - vec[1]*np.sin(deg),
        vec[0]*np.sin(deg) + vec[1]*np.cos(deg),
        vec[2]
    ])



def transTo(target,n=N): #TODO: make max step length or 

    assert(target.shape==(6,3))
    initPos = np.zeros((6, 3))
    for i in range(6):
        res, initPos[i] = vrep.simxGetObjectPosition(clientID, S1[i], BCS, vrep.simx_opmode_oneshot_wait)
    delta = (target - initPos)/n
#     print (delta)
    #To make the steps smoother
    for i in range(3):
        initPos += delta/3
        vrep.simxSynchronousTrigger(clientID)
        for j in range(6):
            vrep.simxSetObjectPosition(clientID, Tip_target[j], BCS, initPos[j],vrep.simx_opmode_oneshot_wait)

    for i in range(n-2):
        initPos += delta
        vrep.simxSynchronousTrigger(clientID)
        for j in range(6):
            vrep.simxSetObjectPosition(clientID, Tip_target[j], BCS, initPos[j],vrep.simx_opmode_oneshot_wait)


    #To make the steps smoother
    for i in range(3):
        initPos += delta/3
        vrep.simxSynchronousTrigger(clientID)
        for j in range(6):
            vrep.simxSetObjectPosition(clientID, Tip_target[j], BCS, initPos[j],vrep.simx_opmode_oneshot_wait)
    for j in range(6):
        vrep.simxSetObjectPosition(clientID, Tip_target[j], BCS, target[j],vrep.simx_opmode_oneshot_wait)
    vrep.simxSynchronousTrigger(clientID)

basAng = [1,3,5,-1,-3,-5]
basAng = np.array(basAng)*math.pi/6
def detork(target):
    """
    make the position have no zhuan dong
    """
    ang = np.zeros(6)
    for i in range(0,6):
        ang[i] = math.atan2(target[i][1],target[i][0])
    deg = ave_ang(ang-basAng)
    return deg
def turn_peb(target,deg):
    """
    turn the target vector deg
    """
    for i in range(6):        
        target[i] = turnVec(target[i],-deg)
    return target

def three_step_delta(newpos_delta,side,peb=None):
    """
    newpos is the difference between the new position and the present position of the three peds
    3*3, the z
    side = 0 or 1
    when peb is None assume that the body position is above the middle of the foot (x,y)s.
    peb: shape(2,3) peb[0]: the body target x,y,z position peb[1]: the body oula target angle
    """
    height = 0.25
    if(CLIP):
        newpos_delta = np.clip(newpos_delta,-0.1,0.1)

    if(peb is None):
        avedelta = np.sum(newpos_delta,axis=0)/6 
    else:
        avedelta = peb[0]
    #lift up:
    initPos = np.zeros((6, 3))
    for i in range(6):
        res, initPos[i] = vrep.simxGetObjectPosition(clientID, S1[i], BCS, vrep.simx_opmode_oneshot_wait)
    target = initPos
    for i in range(6):
        if(i%2==side):
            target[i][2] +=height
    transTo(target)

    target = initPos-avedelta
    for i in range(6):
        if(i%2==side):
            target[i] += newpos_delta[int(i/2)]
    if(peb  is None):
        deg = detork(target)
    else:
        deg = peb[1][2]
    target = turn_peb(target,deg)
    transTo(target)
    for i in range(6):
        if(i%2==side):
            target[i][2] -=height
    transTo(target)

def three_step(newpos,side):
    """
    newpos如果shape是（5,3）的话，意味着后面还有peb
    """
    initPos = np.zeros((3, 3))
    for i in range(side,6,2):
        res,initPos[int(i/2)]=vrep.simxGetObjectPosition(clientID, S1[i], BCS, vrep.simx_opmode_oneshot_wait)
    if(newpos.shape==(3,3)):
        three_step_delta(newpos[:3]-initPos,side)
    else:
        three_step_delta(newpos[:3]-initPos,side,newpos[3:])

def print_steps():
    import matplotlib.pyplot as plt
    x=[]
    y = []
    for i in range(6):
        res, Pos = vrep.simxGetObjectPosition(clientID, S1[i], BCS, vrep.simx_opmode_oneshot_wait)
        x.append(Pos[0])
        y.append(Pos[1])
    plt.plot(x,y,"d")
    plt.show()


def walk_a_step(length=0.3,deg=0,peb=None):
    x = length*math.cos(deg)
    y = length*math.sin(deg)
    if(peb is not None):
        peb = peb/2
    three_step_delta(np.array([[x,y,0] for i in range(3)]),0,peb)
    three_step_delta(np.array([[x,y,0] for i in range(3)]),1,peb)

def turn_a_deg(deg,peb = None):
    target = np.zeros((3,3))
    if(peb is not None):
        peb = peb/2
    for step in range(2):
        for i in range(step,6,2):
            res,target[int(i/2)]=vrep.simxGetObjectPosition(clientID, S1[i], BCS, vrep.simx_opmode_oneshot_wait)
        for i in range(3):
            target[i] = turnVec(target[i],deg)
        if(peb is not None):
            target = np.concatenate((target,peb))
        three_step(target,step)




print('Program started')
vrep.simxFinish(-1) # just in case, close all opened connections
clientID=vrep.simxStart('127.0.0.1',19997,True,True,-500000,5) # Connect to V-REP, set a very large time-out for blocking commands
if clientID!=-1:
    print ('Connected to remote API server')
    res = vrep.simxSynchronous(clientID, True)

    emptyBuff = bytearray()

    # Start the simulation:
    vrep.simxStartSimulation(clientID, vrep.simx_opmode_oneshot_wait)
    # ???
    res, U4 = vrep.simxGetObjectHandle(clientID, 'J11R', vrep.simx_opmode_blocking)
    res, U5 = vrep.simxGetObjectHandle(clientID, 'shaft19', vrep.simx_opmode_blocking)
    # 摄像机
    res, kinect_depth_camera = vrep.simxGetObjectHandle(clientID, 'kinect_depth', vrep.simx_opmode_blocking)
    res, kinect_rgb_camera = vrep.simxGetObjectHandle(clientID, 'kinect_rgb', vrep.simx_opmode_blocking)
    res, kinect_joint = vrep.simxGetObjectHandle(clientID, 'kinect_joint', vrep.simx_opmode_blocking)
    #Retrive the body coordinate system
    # 坐标系 ????
    res, GCS = vrep.simxGetObjectHandle(clientID, 'GCS', vrep.simx_opmode_blocking)
    res, BCS = vrep.simxGetObjectHandle(clientID, 'BCS', vrep.simx_opmode_blocking)
    res, goal = vrep.simxGetObjectHandle(clientID, 'Goal', vrep.simx_opmode_blocking)
    # Retrive the poles
    # 18个腿上的杆
    pole = np.zeros(19, dtype='int32')
    for i in range(1, 19):
        res, pole[i] = vrep.simxGetObjectHandle(clientID, 'P' + str(i), vrep.simx_opmode_blocking)

    # Barrier = np.zeros(12, dtype='int32')
    # for i in range(0, 12):
    #     res, Barrier[i] = vrep.simxGetObjectHandle(clientID, 'Barrier' + str(i), vrep.simx_opmode_blocking)

    Wall = np.zeros(6, dtype='int32')
    for i in range(0, 6):
        res, Wall[i] = vrep.simxGetObjectHandle(clientID, 'Wall' + str(i), vrep.simx_opmode_blocking)

    Fence = np.zeros(2, dtype='int32')
    for i in range(0, 2):
        res, Fence[i] = vrep.simxGetObjectHandle(clientID, 'Fence' + str(i), vrep.simx_opmode_blocking)


    #Retrive the U1
    # 在腿和主题连接处。？？？
    U1 = np.zeros(6, dtype='int32')
    for i in range(0, 6):
        res, U1[i] = vrep.simxGetObjectHandle(clientID, 'Hip' + str(i + 1), vrep.simx_opmode_blocking)
    # Retrive the U2
    # 每根腿。最上层
    U2 = np.zeros(6, dtype='int32')
    res, U2[0] = vrep.simxGetObjectHandle(clientID, 'J21R', vrep.simx_opmode_blocking)
    for i in range(1, 6):
        res, U2[i] = vrep.simxGetObjectHandle(clientID, 'J21R' + str(i - 1), vrep.simx_opmode_blocking)
    # Retrive the U3
    # 每根腿，最上层
    U3 = np.zeros(6, dtype='int32')
    res, U3[0] = vrep.simxGetObjectHandle(clientID, 'J31R', vrep.simx_opmode_blocking)
    for i in range(1, 6):
        res, U3[i] = vrep.simxGetObjectHandle(clientID, 'J31R' + str(i - 1), vrep.simx_opmode_blocking)
    # Retrive the target Dummy
    # ？？？？？
    target_Dummy = np.zeros(6, dtype='int32')
    for i in range(0, 6):
        res, target_Dummy[i] = vrep.simxGetObjectHandle(clientID, 'target_Dummy' + str(i + 1),
                                                        vrep.simx_opmode_blocking)

    # Retrive the S1
    # Tip 末梢 坐标系
    S1 = np.zeros(6, dtype='int32')
    for i in range(0, 6):
        res, S1[i] = vrep.simxGetObjectHandle(clientID, 'Tip' + str(i + 1), vrep.simx_opmode_blocking)
    # 坐标系，与 Tip上边连接在一起
    Tip_target = np.zeros(6, dtype='int32')
    for i in range(0, 6):
        res, Tip_target[i] = vrep.simxGetObjectHandle(clientID, 'TipTarget' + str(i + 1), vrep.simx_opmode_blocking)


if __name__=="__main__":
    #test
    recover( n=min(N,30))
    # walk_a_step(0.3,math.pi/2,np.array([[0,0,0],[0,0,0]]))
    walk_a_step(0.3,0,np.array([[0.3,0,0],[0,0,0]]))
    


    turn_a_deg(0.2,peb=np.array([[0,0,0],[0,0,0.2]]))

    
    # three_step(np.array([[-0.01539664 ,-0.07759521  ,0.        ],
    #                 [-0.09819948 ,-0.05909955  ,0.        ],
    #                 [ 0.10317233 ,-0.05715271  ,0.        ]]),0)
    