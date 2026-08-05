# -*- coding: utf-8 -*-

import datetime
import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QDialog, QMessageBox
from PySide6.QtGui import QPainter, QPen, QColor, QPolygonF
from PySide6.QtCore import Qt, QPoint, QPointF, QThread, QTimer
from listening import SocketWorker
# from wordsOCR import get_enemy_bearing_OCR, take_screenshot
from remoteOCR import operateAwacsMarkRemoteWorker
from remoteTeam import operateTeamMateMarkRemoteWorker
from serverInfor import serverInforDetail
from wordsOCRFlask import take_screenshot
from utils import calculate_bearing_and_distance,  drawEnemyPlaneByBearingAndDistanceAbsScale, \
    drawEnemyPlaneByBearingAndDistanceSAScale, drawFriendPlaneByBearingAndDistanceSAScale,\
        drawFriendPlaneByBearingAndDistanceAbsScale, serverIsReachable, get_config_path

from window import Ui_MA
import math
import os
import time
from arsInputDialog import Ui_argsDialog
os.chdir(os.path.dirname(__file__))
from AWACASMARK_config import Config

timerTime = 1000  # 计时器时间间隔，单位为毫秒
screenTime = 400  # 截图计时器时间间隔，单位为毫秒
teamTime = 4000  # 队伍信息计时器时间间隔，单位为毫秒

default_host = "121.41.75.139"
default_port = 10386

# 程序启动随机生成一组整数作为ID
import random

program_id = random.randint(1000000000, 9999999999)

class ArgsDialog(QDialog, Ui_argsDialog):
    def __init__(self, parent=None):
        super(ArgsDialog, self).__init__(parent)
        self.setupUi(self)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        
        self.testButton.clicked.connect(self.testConnection)
        
        self.showEnemyCheckBox.stateChanged.connect(self.enemyCheckBoxChanged)
        self.showFriendCheckBox.stateChanged.connect(self.friendCheckBoxChanged)
        self.serverCheckBox.stateChanged.connect(self.serverCheckBoxChanged)
        
        self.showFriendCheckBox.setChecked(Config["showFriend"])
        self.teamCodeEdit.setEnabled(Config["showFriend"])
        
        self.serverCheckBox.setChecked(Config["isDefaultServer"])
        self.serverHostEdit.setEnabled(not Config["isDefaultServer"])
        self.portEdit.setEnabled(not Config["isDefaultServer"])
        
        self.showEnemyCheckBox.setChecked(Config["showEnemy"])
        self.xEdit.setEnabled(Config["showEnemy"])
        self.yEdit.setEnabled(Config["showEnemy"])
        self.widthEdit.setEnabled(Config["showEnemy"])
        self.heightEdit.setEnabled(Config["showEnemy"])
        
        
        
    def enemyCheckBoxChanged(self, event):
        isChecked = self.showEnemyCheckBox.isChecked()
        self.xEdit.setEnabled(isChecked)
        self.yEdit.setEnabled(isChecked)
        self.widthEdit.setEnabled(isChecked)
        self.heightEdit.setEnabled(isChecked)
        Config["showEnemy"] = isChecked
        print(f"showEnemy: {Config['showEnemy']}")
        
    def friendCheckBoxChanged(self, event):
        isChecked = self.showFriendCheckBox.isChecked()
        self.teamCodeEdit.setEnabled(isChecked)
        Config["showFriend"] = isChecked
        print(f"showFriend: {Config['showFriend']}")
    
    def serverCheckBoxChanged(self, event):
        isChecked = self.serverCheckBox.isChecked()
        self.serverHostEdit.setEnabled(not isChecked)
        self.portEdit.setEnabled(not isChecked)
        Config["isDefaultServer"] = isChecked
        print(f"isDefaultServer: {Config['isDefaultServer']}")
        
    def testConnection(self):
        self.logShow.setText("正在测试连接...")
        if self.serverCheckBox.isChecked():
            host = default_host
            port = default_port
        else:
            host = self.serverHostEdit.text()
            port = int(self.portEdit.text())
        isReachable = serverIsReachable(host, port)
        print(f"服务器 {host}:{port} 可达: {isReachable}")
        # 弹窗显示测试结果
        if isReachable:
            self.logShow.setText("连接测试成功！")
        else:
            self.logShow.setText("连接测试失败！")


class Winform(QMainWindow, Ui_MA):
    def __init__(self, parent=None, center_x=200, center_y=200, num_circles=5):
        super(Winform, self).__init__(parent)
        self.setupUi(self)
        # self.setWindowTitle("QPainter示例")
        self.resize(400, 400)
        self.comboBox.addItems(['中心','直对','中心直对'])
        
        
        self.comboBox.currentIndexChanged.connect(self.update)  # 切换模式时刷新界面
        # self.comboBox.textActivated.connect(self.onDraw)
        
        self.scaleComboBox.addItems(['50km', '100km', '200km'])
        self.scaleComboBox.currentIndexChanged.connect(self.update)  # 切换比例尺时刷新界面
        
        # added by test
        self.center_x = center_x
        self.center_y = center_y
        self.num_circles = num_circles          # 同心圆数量
        self.angle_step = 30                    # 角度间隔（度）
        
        
        # 窗口置顶
        self.frontCheckBox.stateChanged.connect(self.toggle_topmost)
        
        # 透明度修改
        self.opcSizeVerticalSlider.setMinimum(20)    # 最小透明度 20%
        self.opcSizeVerticalSlider.setMaximum(100)   # 最大透明度 100%
        self.opcSizeVerticalSlider.setValue(100)     # 初始值 100% 完全不透明
        # self.opcSizeVerticalSlider.setTickPosition(QSlider.TickPosition.TicksBothSides)
        self.opcSizeVerticalSlider.valueChanged.connect(self.change_opacity)
        
        #self.startButton按下
        self.startButton.clicked.connect(self.startMission)
        #self.endButton初始不可点击
        self.endButton.setEnabled(False)
        self.endButton.clicked.connect(self.endMission)  # 点击结束按钮关闭窗口
        
        
        ## 多线程
        self.plane_data = {            "heading": 270,
            "x": 0,
            "y": 2000,
            "z": 0,
            "height": 0}  # 用于存储飞机数据的字典
        self.thread = None
        self.worker = None
        
        self.threadOCRFlask = None
        self.workerOCRFlask = None
        
        self.threadTeamFlask = None
        self.workerTeamFlask = None
        
        self.radius_distance = {
            "km": 50,
            "nm": 25
        }
        
        self.showMetrics = Config["showMetrics"]
        self.showMetricsComboBox.addItems(['km', 'nm'])
        self.showMetricsComboBox.currentIndexChanged.connect(self.showMetricsChanged)  # 切换显示单位时刷新界面
        
        self.argsReady = False
        self.inforButton.clicked.connect(self.showAndInputInfor)

        ## 计时任务，间隔一秒
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.operateAwacsMark)  # 每秒刷新界面
        
        self.team_members = []  # 用于存储队友信息的列表
        self.timerTeam = QTimer(self)
        self.timerTeam.timeout.connect(self.operateTeamMate)  # 每秒刷新界面
        
        self.timerScreen = QTimer(self)
        self.timerScreen.timeout.connect(self.takeScreenShotTimer)  # 每秒刷新界面
        self.screenShortList = []
        
        ## 共享
        self.message_dic = {}
        self.bullseye_dic = {}


    def paintEvent(self, event):
        # print("paintEvent triggered")
        # print(event)
        if self.comboBox.currentIndex() == 0:  # NGAS
            self.paintInit(event)
        elif self.comboBox.currentIndex() == 1:  # SA
            self.paintSA(event)
        elif self.comboBox.currentIndex() == 2:  # Center-SA
            self.paintSACenter(event)

    def paintInit(self,event):
        with QPainter(self) as painter: 
            painter.setRenderHint(QPainter.Antialiasing)  # 抗锯齿
            
            scale = (2**self.scaleComboBox.currentIndex()) * self.radius_distance[self.showMetrics]  # 根据选择的比例尺设置最大距离
            # print("当前比例尺：", scale, self.showMetrics)
            # 获取窗口中心（如果未指定中心点，则使用窗口中心）
            if self.center_x is None or self.center_y is None:
                width = self.width()
                height = self.height()
                center_x = width // 2
                center_y = height // 2
            else:
                center_x = self.center_x
                center_y = self.center_y 
            
            radius_interval = min(self.width(), self.height()) // (2 * self.num_circles + 1)  # 圆间距
            # 设置画笔：虚线样式
            pen = QPen()
            pen.setColor(QColor(76, 153, 0))  # 绿色，类似雷达屏幕
            pen.setWidth(1)
            # 设置虚线样式：5像素画线，3像素间隔
            pen.setStyle(Qt.DashLine)
            pen.setDashPattern([5, 3])
            
            painter.setPen(pen)
            
            # 1. 绘制同心圆
            for i in range(1, self.num_circles + 1):
                radius = i * radius_interval
                # 绘制圆
                painter.drawEllipse(QPoint(center_x, center_y), radius, radius)
            
            # 2. 绘制径向直线（从中心向外延伸到最大圆）
            max_radius = self.num_circles * radius_interval
            
            for angle_deg in range(0, 360, self.angle_step):
                # 角度转换为弧度
                angle_rad = math.radians(angle_deg)
                
                # 计算最大圆上的终点坐标
                end_x = center_x + max_radius * math.cos(angle_rad)
                end_y = center_y + max_radius * math.sin(angle_rad)
                
                # 从中心画线到终点
                painter.drawLine(center_x, center_y, end_x, end_y)
            
            
            
            # -------------------------------------
            # 3. 绘制方向标识和角度文字
            font = painter.font()
            font.setPointSize(12)
            painter.setFont(font)

            # 定义地理方向（上北下南）
            directions = {
                'N': 0,    # 北（向上）
                'S': 180,  # 南（向下）
                'E': 90,   # 东（向右）
                'W': 270   # 西（向左）
            }

            text_offset = 15

            # 绘制方向标识
            for direction, angle_deg in directions.items():
                # 转换为数学角度
                math_angle_deg = (90 + angle_deg) % 360
                angle_rad = math.radians(math_angle_deg)
                
                text_x = center_x - (max_radius + text_offset) * math.cos(angle_rad)
                text_y = center_y - (max_radius + text_offset) * math.sin(angle_rad)
                painter.drawText(text_x - 10, text_y + 5, direction)

            # 绘制 30° 倍数的角度文字
            angle_text_offset = 20
            angle_interval = 30

            for angle_deg in range(0, 360, angle_interval):
                if angle_deg in directions.values():
                    continue
                
                # 转换为数学角度
                math_angle_deg = (90 + angle_deg) % 360
                angle_rad = math.radians(math_angle_deg)
                
                text_x = center_x - (max_radius + angle_text_offset) * math.cos(angle_rad)
                text_y = center_y - (max_radius + angle_text_offset) * math.sin(angle_rad)
                painter.drawText(text_x - 15, text_y + 7, f"{angle_deg}°")  
            # -------------------------------------
            
            
            # 可选：添加一个中心点标记
            pen.setStyle(Qt.SolidLine)
            pen.setColor(QColor(204, 0, 0))  # 红色中心点
            painter.setPen(pen)
            painter.drawEllipse(QPoint(center_x, center_y), 3, 3)
            
            # 在中心点附近绘制文字，文字为plane_data中的y值，代表数字高度
            font.setPointSize(5)
            painter.setFont(font)
            painter.setPen(QColor(255, 0, 0, 128))  
            plane_height = self.plane_data['y']
            if self.showMetrics == "nm":
                plane_height = plane_height / 1000 * 3.28084  # 米转英尺
            else:
                plane_height = plane_height / 1000  # 米转千米
            painter.drawText(center_x + 10, center_y - 10, f"{plane_height:.1f}")

            
            # 添加箭头表示前进方向
            arrow_length = radius_interval/4  # 箭头长度
            direction_angle = self.plane_data["heading"] + 90  # 方向角度（0度向右，90度向上，180度向左，270度向下）
            # 或者你可以使用变量来存储方向

            # 将角度转换为弧度
            angle_rad = math.radians(direction_angle)

            # 计算箭头终点（头部）
            arrow_end_x = center_x - arrow_length * math.cos(angle_rad)
            arrow_end_y = center_y - arrow_length * math.sin(angle_rad)  # Y轴向下为正，所以减号

            # 绘制箭头线
            pen.setColor(QColor(204, 0, 0))  # 红色箭头
            pen.setWidth(2)
            painter.setPen(pen)
            painter.drawLine(center_x, center_y, arrow_end_x, arrow_end_y)

            # 绘制箭头头部（三角形）
            arrow_head_size = radius_interval/20  # 箭头头部大小
            arrow_angle = math.radians(30)  # 箭头张开角度

            # 计算箭头头部的两个点
            angle1 = angle_rad + arrow_angle
            angle2 = angle_rad - arrow_angle

            point1_x = arrow_end_x - arrow_head_size * math.cos(angle1)
            point1_y = arrow_end_y + arrow_head_size * math.sin(angle1)

            point2_x = arrow_end_x - arrow_head_size * math.cos(angle2)
            point2_y = arrow_end_y + arrow_head_size * math.sin(angle2)

            # 绘制箭头头部三角形
            arrow_head = QPolygonF([
                QPointF(arrow_end_x, arrow_end_y),
                QPointF(point1_x, point1_y),
                QPointF(point2_x, point2_y)
            ])
            painter.setBrush(QColor(0, 0, 255))  # 填充蓝色s
            painter.drawPolygon(arrow_head)
            
            # test-----------------
            # drawEnemyPlaneByBearingAndDistanceAbsScale(painter, center_x, center_y,  
            #                                        112, 40, 90, 8, scale, radius_interval, max_radius, 0, 1)
            # drawEnemyPlaneByBearingAndDistanceAbsScale(painter, center_x, center_y,  
            #                                        359, 40, -1, 2, scale, radius_interval, max_radius, 4, 1)
            
            message_dic_copy = self.message_dic.copy()
            plane_data_copy = self.plane_data.copy()
            bullseye_dic_copy = self.bullseye_dic.copy()
            team_members_copy = self.team_members.copy()
            
            if Config["showFriend"]:
                drawFriendPlaneByBearingAndDistanceAbsScale(painter, center_x, center_y, plane_data_copy,
                                                           team_members_copy, scale, radius_interval, 
                                                           max_radius)
            
            
            for key in message_dic_copy:
                message = message_dic_copy[key]
                if message["times"] <= 1:
                    continue
                distance, bearing = calculate_bearing_and_distance(plane_data_copy['x'], plane_data_copy['z'], 
                                                                message["x"], message["z"])
                # print("敌机距离和方位：", distance, bearing)
                if self.showMetrics == "nm":
                    distance = distance /  1852
                    if Config["awacsMetricUnit"] == "nm":
                        enemy_altitude = message["enemy_altitude"] / 1000
                    else:
                        enemy_altitude = message["enemy_altitude"] / 1000 * 3.28084  # 米转英尺
                else:
                    distance = distance / 1000
                    if Config["awacsMetricUnit"] == "nm":
                        enemy_altitude = (message["enemy_altitude"] / 1000) / 3.28084  # 英尺转米
                    else:
                        enemy_altitude = message["enemy_altitude"] / 1000
                eclapseTime = (int(time.time()) - message["timeStamp"])//10
                eclapseTime = eclapseTime if eclapseTime < 6 else 6
                drawEnemyPlaneByBearingAndDistanceAbsScale(painter, center_x, center_y,  
                                                bearing, distance, message,
                                                enemy_altitude, scale, radius_interval,
                                                max_radius, eclapseTime)
            for key in bullseye_dic_copy:
                message = bullseye_dic_copy[key]
                if message["times"] <= 1:
                    continue
                distance, bearing = calculate_bearing_and_distance(plane_data_copy['x'], plane_data_copy['z'], 
                                                                message["x"], message["z"])
                if self.showMetrics == "nm":
                    distance = distance /  1852
                    if Config["awacsMetricUnit"] == "nm":
                        bulls_enemy_altitude = message["bulls_enemy_altitude"] / 1000
                    else:
                        bulls_enemy_altitude = message["bulls_enemy_altitude"] / 1000 * 3.28084  # 米转英尺
                else:
                    distance = distance / 1000
                    if Config["awacsMetricUnit"] == "nm":
                        bulls_enemy_altitude = (message["bulls_enemy_altitude"] / 1000) / 3.28084  # 英尺转米
                    else:
                        bulls_enemy_altitude = message["bulls_enemy_altitude"] / 1000
                        
                eclapseTime = (int(time.time()) - message["timeStamp"])//10
                eclapseTime = eclapseTime if eclapseTime < 6 else 6

                drawEnemyPlaneByBearingAndDistanceAbsScale(painter, center_x, center_y, 
                                                bearing, distance, message,
                                                bulls_enemy_altitude, scale, radius_interval,
                                                max_radius, eclapseTime)
        
        
    
    # def resizeEvent(self, event):
    #     """窗口大小改变时自动更新"""
    #     self.update()

    def paintSA(self, event):
        with QPainter(self) as painter: 
            painter.setRenderHint(QPainter.Antialiasing)  # 抗锯齿
            
            scale = (2**self.scaleComboBox.currentIndex()) * self.radius_distance[self.showMetrics]  # 根据选择的比例尺设置最大距离
        
            # print("当前比例尺：", scale, self.showMetrics)
            # 获取窗口中心（如果未指定中心点，则使用窗口中心）
            if self.center_x is None or self.center_y is None:
                width = self.width()
                height = self.height()
                center_x = width // 2
                center_y = height * 5 // 6
            else:
                center_x = self.center_x
                center_y = self.center_y * 10 // 6
            
            radius_interval = self.width() // (2 * self.num_circles + 1)  # 圆间距
            # 设置画笔：虚线样式
            pen = QPen()
            pen.setColor(QColor(76, 153, 0))  # 绿色，类似雷达屏幕
            pen.setWidth(1)
            # 设置虚线样式：5像素画线，3像素间隔
            pen.setStyle(Qt.DashLine)
            pen.setDashPattern([5, 3])
            
            painter.setPen(pen)
            
            # 1. 绘制同心圆
            for i in range(1, self.num_circles + 1):
                radius = i * radius_interval
                # 绘制圆
                painter.drawEllipse(QPoint(center_x, center_y), radius, radius)
            
            # 2. 绘制径向直线（从中心向外延伸到最大圆）
            max_radius = self.num_circles * radius_interval
            
            for angle_deg in range(0, 360, self.angle_step):
                # 角度转换为弧度
                angle_rad = math.radians(angle_deg)
                
                # 计算最大圆上的终点坐标
                end_x = center_x + max_radius * math.cos(angle_rad)
                end_y = center_y + max_radius * math.sin(angle_rad)
                
                # 从中心画线到终点
                painter.drawLine(center_x, center_y, end_x, end_y)
            
                    # 3. 绘制方向标识和角度文字
            font = painter.font()
            font.setPointSize(12)
            painter.setFont(font)

            # 定义地理方向（上北下南）
            directions = {
                'N': 0,    # 北（向上）
                'S': 180,  # 南（向下）
                'E': 90,   # 东（向右）
                'W': 270   # 西（向左）
            }

            text_offset = 15

            # 绘制方向标识
            for direction, angle_deg in directions.items():
                # 转换为数学角度
                math_angle_deg = (90 + angle_deg - self.plane_data['heading']) % 360
                angle_rad = math.radians(math_angle_deg)
                
                text_x = center_x - (max_radius + text_offset) * math.cos(angle_rad)
                text_y = center_y - (max_radius + text_offset) * math.sin(angle_rad)
                painter.drawText(text_x - 10, text_y + 5, direction)

            # 绘制 30° 倍数的角度文字
            angle_text_offset = 20
            angle_interval = 30

            for angle_deg in range(0, 360, angle_interval):
                if angle_deg in directions.values():
                    continue
                
                # 转换为数学角度
                math_angle_deg = (90 + angle_deg - self.plane_data['heading']) % 360
                angle_rad = math.radians(math_angle_deg)
                
                text_x = center_x - (max_radius + angle_text_offset) * math.cos(angle_rad)
                text_y = center_y - (max_radius + angle_text_offset) * math.sin(angle_rad)
                painter.drawText(text_x - 15, text_y + 7, f"{angle_deg}°")  
            # -------------------------------------
            
            
            # 可选：添加一个中心点标记
            pen.setStyle(Qt.SolidLine)
            pen.setColor(QColor(204, 0, 0))  # 红色中心点
            painter.setPen(pen)
            painter.drawEllipse(QPoint(center_x, center_y), 3, 3)

            # 在中心点附近绘制文字，文字为plane_data中的y值，代表数字高度
            font.setPointSize(5)
            painter.setFont(font)
            painter.setPen(QColor(255, 0, 0, 128))  
            plane_height = self.plane_data['y']
            if self.showMetrics == "nm":
                plane_height = plane_height / 1000 * 3.28084  # 米转英尺
            else:
                plane_height = plane_height / 1000  # 米转千米
            painter.drawText(center_x + 10, center_y - 10, f"{plane_height:.1f}")
            
            # 添加箭头表示前进方向
            arrow_length = radius_interval/4  # 箭头长度
            direction_angle = 0 + 90 # 方向角度（0度向右，90度向上，180度向左，270度向下）
            # 或者你可以使用变量来存储方向

            # 将角度转换为弧度
            angle_rad = math.radians(direction_angle)

            # 计算箭头终点（头部）
            arrow_end_x = center_x + arrow_length * math.cos(angle_rad)
            arrow_end_y = center_y - arrow_length * math.sin(angle_rad)  # Y轴向下为正，所以减号

            # 绘制箭头线
            pen.setColor(QColor(204, 0, 0))  # 蓝色箭头
            pen.setWidth(2)
            painter.setPen(pen)
            painter.drawLine(center_x, center_y, arrow_end_x, arrow_end_y)

            # 绘制箭头头部（三角形）
            arrow_head_size = radius_interval/20  # 箭头头部大小
            arrow_angle = math.radians(30)  # 箭头张开角度

            # 计算箭头头部的两个点
            angle1 = angle_rad + arrow_angle
            angle2 = angle_rad - arrow_angle

            point1_x = arrow_end_x - arrow_head_size * math.cos(angle1)
            point1_y = arrow_end_y + arrow_head_size * math.sin(angle1)

            point2_x = arrow_end_x - arrow_head_size * math.cos(angle2)
            point2_y = arrow_end_y + arrow_head_size * math.sin(angle2)

            # 绘制箭头头部三角形
            arrow_head = QPolygonF([
                QPointF(arrow_end_x, arrow_end_y),
                QPointF(point1_x, point1_y),
                QPointF(point2_x, point2_y)
            ])
            painter.setBrush(QColor(0, 0, 255))  # 填充蓝色
            painter.drawPolygon(arrow_head)
            
                    # test-----------------
            # drawEnemyPlaneByBearingAndDistanceSAScale(painter, center_x, center_y,  self.plane_data['heading'],
            #                                        300, 40, -1, 9, scale, radius_interval, max_radius, 0)
            # drawEnemyPlaneByBearingAndDistanceSAScale(painter, center_x, center_y,  self.plane_data['heading'],
            #                                        359, 40, 270, 9, scale, radius_interval, max_radius, 4)
            message_dic_copy = self.message_dic.copy()
            plane_data_copy = self.plane_data.copy()
            bullseye_dic_copy = self.bullseye_dic.copy()
            team_members_copy = self.team_members.copy()
            
            
            if Config["showFriend"]:
                drawFriendPlaneByBearingAndDistanceSAScale(painter, center_x, center_y, plane_data_copy,
                                                           team_members_copy, scale, radius_interval, 
                                                           max_radius)
            
            for key in message_dic_copy:
                message = message_dic_copy[key]
                if message["times"] <= 1:
                    continue
                distance, bearing = calculate_bearing_and_distance(plane_data_copy['x'], plane_data_copy['z'], 
                                                                message["x"], message["z"])
                if self.showMetrics == "nm":
                    distance = distance /  1852
                    if Config["awacsMetricUnit"] == "nm":
                        enemy_altitude = message["enemy_altitude"] / 1000
                    else:
                        enemy_altitude = message["enemy_altitude"] / 1000 * 3.28084  # 米转英尺
                else:
                    distance = distance / 1000
                    if Config["awacsMetricUnit"] == "nm":
                        enemy_altitude = (message["enemy_altitude"] / 1000) / 3.28084  # 英尺转米
                    else:
                        enemy_altitude = message["enemy_altitude"] / 1000
                        
                eclapseTime = (int(time.time()) - message["timeStamp"])//10
                eclapseTime = eclapseTime if eclapseTime < 6 else 6
                drawEnemyPlaneByBearingAndDistanceSAScale(painter, center_x, center_y, plane_data_copy['heading'], 
                                                bearing, distance, message,
                                                enemy_altitude, scale, radius_interval,
                                                max_radius, eclapseTime)
            for key in bullseye_dic_copy:
                message = bullseye_dic_copy[key]
                if message["times"] <= 1:
                    continue
                distance, bearing = calculate_bearing_and_distance(plane_data_copy['x'], plane_data_copy['z'], 
                                                                message["x"], message["z"])
                if self.showMetrics == "nm":
                    distance = distance /  1852
                    if Config["awacsMetricUnit"] == "nm":
                        bulls_enemy_altitude = message["bulls_enemy_altitude"] / 1000
                    else:
                        bulls_enemy_altitude = message["bulls_enemy_altitude"] / 1000 * 3.28084  # 米转英尺
                else:
                    distance = distance / 1000
                    if Config["awacsMetricUnit"] == "nm":
                        bulls_enemy_altitude = (message["bulls_enemy_altitude"] / 1000) / 3.28084  # 英尺转米
                    else:
                        bulls_enemy_altitude = message["bulls_enemy_altitude"] / 1000
                eclapseTime = (int(time.time()) - message["timeStamp"])//10
                eclapseTime = eclapseTime if eclapseTime < 6 else 6
                drawEnemyPlaneByBearingAndDistanceSAScale(painter, center_x, center_y, plane_data_copy['heading'], 
                                                bearing, distance, message,
                                                bulls_enemy_altitude, scale, radius_interval,
                                                max_radius, eclapseTime)
            
            # test
            # painter.fillRect(self.rect(), Qt.black)
            # painter.eraseRect(self.rect())
            # start_angle = 30 * 16
            # arc_length = 120 * 16
            # rect = QRect(50, 60, 80, 60)
            # painter.drawChord(rect, start_angle, arc_length)
    def paintSACenter(self, event):
        with QPainter(self) as painter: 
            painter.setRenderHint(QPainter.Antialiasing)  # 抗锯齿
            
            scale = (2**self.scaleComboBox.currentIndex()) * self.radius_distance[self.showMetrics]  # 根据选择的比例尺设置最大距离
        
            # print("当前比例尺：", scale, self.showMetrics)
            # 获取窗口中心（如果未指定中心点，则使用窗口中心）
            if self.center_x is None or self.center_y is None:
                width = self.width()
                height = self.height()
                center_x = width // 2
                center_y = height // 2
            else:
                center_x = self.center_x
                center_y = self.center_y 
            
            radius_interval = self.width() // (2 * self.num_circles + 1)  # 圆间距
            # 设置画笔：虚线样式
            pen = QPen()
            pen.setColor(QColor(76, 153, 0))  # 绿色，类似雷达屏幕
            pen.setWidth(1)
            # 设置虚线样式：5像素画线，3像素间隔
            pen.setStyle(Qt.DashLine)
            pen.setDashPattern([5, 3])
            
            painter.setPen(pen)
            
            # 1. 绘制同心圆
            for i in range(1, self.num_circles + 1):
                radius = i * radius_interval
                # 绘制圆
                painter.drawEllipse(QPoint(center_x, center_y), radius, radius)
            
            # 2. 绘制径向直线（从中心向外延伸到最大圆）
            max_radius = self.num_circles * radius_interval
            
            for angle_deg in range(0, 360, self.angle_step):
                # 角度转换为弧度
                angle_rad = math.radians(angle_deg)
                
                # 计算最大圆上的终点坐标
                end_x = center_x + max_radius * math.cos(angle_rad)
                end_y = center_y + max_radius * math.sin(angle_rad)
                
                # 从中心画线到终点
                painter.drawLine(center_x, center_y, end_x, end_y)
            
                    # 3. 绘制方向标识和角度文字
            font = painter.font()
            font.setPointSize(12)
            painter.setFont(font)

            # 定义地理方向（上北下南）
            directions = {
                'N': 0,    # 北（向上）
                'S': 180,  # 南（向下）
                'E': 90,   # 东（向右）
                'W': 270   # 西（向左）
            }

            text_offset = 15

            # 绘制方向标识
            for direction, angle_deg in directions.items():
                # 转换为数学角度
                math_angle_deg = (90 + angle_deg - self.plane_data['heading']) % 360
                angle_rad = math.radians(math_angle_deg)
                
                text_x = center_x - (max_radius + text_offset) * math.cos(angle_rad)
                text_y = center_y - (max_radius + text_offset) * math.sin(angle_rad)
                painter.drawText(text_x - 10, text_y + 5, direction)

            # 绘制 30° 倍数的角度文字
            angle_text_offset = 20
            angle_interval = 30

            for angle_deg in range(0, 360, angle_interval):
                if angle_deg in directions.values():
                    continue
                
                # 转换为数学角度
                math_angle_deg = (90 + angle_deg - self.plane_data['heading']) % 360
                angle_rad = math.radians(math_angle_deg)
                
                text_x = center_x - (max_radius + angle_text_offset) * math.cos(angle_rad)
                text_y = center_y - (max_radius + angle_text_offset) * math.sin(angle_rad)
                painter.drawText(text_x - 15, text_y + 7, f"{angle_deg}°")  
            # -------------------------------------
            
            
            # 可选：添加一个中心点标记
            pen.setStyle(Qt.SolidLine)
            pen.setColor(QColor(204, 0, 0))  # 红色中心点
            painter.setPen(pen)
            painter.drawEllipse(QPoint(center_x, center_y), 3, 3)

                        # 在中心点附近绘制文字，文字为plane_data中的y值，代表数字高度
            font.setPointSize(8)
            painter.setFont(font)
            painter.setPen(QColor(255, 0, 0, 128))  
            plane_height = self.plane_data['y']
            if Config["awacsMetricUnit"] == "nm":
                plane_height = plane_height / 1000 * 3.28084  # 米转英尺
            else:
                plane_height = plane_height / 1000  # 米转千米
            painter.drawText(center_x - 8, center_y + 10, f"{plane_height:.1f}")
            
            # 添加箭头表示前进方向
            arrow_length = radius_interval/4  # 箭头长度
            direction_angle = 0 + 90 # 方向角度（0度向右，90度向上，180度向左，270度向下）
            # 或者你可以使用变量来存储方向

            # 将角度转换为弧度
            angle_rad = math.radians(direction_angle)

            # 计算箭头终点（头部）
            arrow_end_x = center_x + arrow_length * math.cos(angle_rad)
            arrow_end_y = center_y - arrow_length * math.sin(angle_rad)  # Y轴向下为正，所以减号

            # 绘制箭头线
            pen.setColor(QColor(204, 0, 0))  # 蓝色箭头
            pen.setWidth(2)
            painter.setPen(pen)
            painter.drawLine(center_x, center_y, arrow_end_x, arrow_end_y)

            # 绘制箭头头部（三角形）
            arrow_head_size = radius_interval/20  # 箭头头部大小
            arrow_angle = math.radians(30)  # 箭头张开角度

            # 计算箭头头部的两个点
            angle1 = angle_rad + arrow_angle
            angle2 = angle_rad - arrow_angle

            point1_x = arrow_end_x - arrow_head_size * math.cos(angle1)
            point1_y = arrow_end_y + arrow_head_size * math.sin(angle1)

            point2_x = arrow_end_x - arrow_head_size * math.cos(angle2)
            point2_y = arrow_end_y + arrow_head_size * math.sin(angle2)

            # 绘制箭头头部三角形
            arrow_head = QPolygonF([
                QPointF(arrow_end_x, arrow_end_y),
                QPointF(point1_x, point1_y),
                QPointF(point2_x, point2_y)
            ])
            painter.setBrush(QColor(0, 0, 255))  # 填充蓝色
            painter.drawPolygon(arrow_head)
            
                    # test-----------------
            # drawEnemyPlaneByBearingAndDistanceSAScale(painter, center_x, center_y,  self.plane_data['heading'],
            #                                        300, 40, -1, 9, scale, radius_interval, max_radius, 0)
            # drawEnemyPlaneByBearingAndDistanceSAScale(painter, center_x, center_y,  self.plane_data['heading'],
            #                                        359, 40, 270, 9, scale, radius_interval, max_radius, 4)
            message_dic_copy = self.message_dic.copy()
            plane_data_copy = self.plane_data.copy()
            bullseye_dic_copy = self.bullseye_dic.copy()
            team_members_copy = self.team_members.copy()
            
            if Config["showFriend"]:
                drawFriendPlaneByBearingAndDistanceSAScale(painter, center_x, center_y, plane_data_copy,
                                                           team_members_copy, scale, radius_interval, 
                                                           max_radius)
            
            for key in message_dic_copy:
                message = message_dic_copy[key]
                if message["times"] <= 1:
                    continue
                distance, bearing = calculate_bearing_and_distance(plane_data_copy['x'], plane_data_copy['z'], 
                                                                message["x"], message["z"])
                if self.showMetrics == "nm":
                    distance = distance /  1852
                    if Config["awacsMetricUnit"] == "nm":
                        enemy_altitude = message["enemy_altitude"] / 1000
                    else:
                        enemy_altitude = message["enemy_altitude"] / 1000 * 3.28084  # 米转英尺
                else:
                    distance = distance / 1000
                    if Config["awacsMetricUnit"] == "nm":
                        enemy_altitude = (message["enemy_altitude"] / 1000) / 3.28084  # 英尺转米
                    else:
                        enemy_altitude = message["enemy_altitude"] / 1000
                        
                eclapseTime = (int(time.time()) - message["timeStamp"])//10
                eclapseTime = eclapseTime if eclapseTime < 6 else 6
                drawEnemyPlaneByBearingAndDistanceSAScale(painter, center_x, center_y, plane_data_copy['heading'], 
                                                bearing, distance, message,
                                                enemy_altitude, scale, radius_interval,
                                                max_radius, eclapseTime)
            for key in bullseye_dic_copy:
                message = bullseye_dic_copy[key]
                if message["times"] <= 1:
                    continue
                distance, bearing = calculate_bearing_and_distance(plane_data_copy['x'], plane_data_copy['z'], 
                                                                message["x"], message["z"])
                if self.showMetrics == "nm":
                    distance = distance /  1852
                    if Config["awacsMetricUnit"] == "nm":
                        bulls_enemy_altitude = message["bulls_enemy_altitude"] / 1000
                    else:
                        bulls_enemy_altitude = message["bulls_enemy_altitude"] / 1000 * 3.28084  # 米转英尺
                else:
                    distance = distance / 1000
                    if Config["awacsMetricUnit"] == "nm":
                        bulls_enemy_altitude = (message["bulls_enemy_altitude"] / 1000) / 3.28084  # 英尺转米
                    else:
                        bulls_enemy_altitude = message["bulls_enemy_altitude"] / 1000
                eclapseTime = (int(time.time()) - message["timeStamp"])//10
                eclapseTime = eclapseTime if eclapseTime < 6 else 6
                drawEnemyPlaneByBearingAndDistanceSAScale(painter, center_x, center_y, plane_data_copy['heading'], 
                                                bearing, distance, message,
                                                bulls_enemy_altitude, scale, radius_interval,
                                                max_radius, eclapseTime)

    # def onDraw(self):
    #     if self.comboBox.currentIndex() == 0:  # NGAS
    #         self.paintEvent = self.paintInit
    #     elif self.comboBox.currentIndex() == 1:  # SA
    #         self.paintEvent = self.paintSA
    #     self.update()
        
    def resizeEvent(self, event):
        """窗口大小改变时自动调用"""
        # 调用父类的 resizeEvent
        super().resizeEvent(event)
        # 触发重画
        # self.update()
        width = self.width()
        height = self.height()
        self.center_x = width // 2
        self.center_y = height // 2
        # self.onDraw()  # 根据当前选择的索引重画
        print("resizeEvent self update")
        self.update()  # 触发重画
        
    def toggle_topmost(self, state):
        # 根据复选框状态设置置顶
        if state == Qt.CheckState.Checked.value:
            self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        else:
            self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, False)
        
        # 重新显示窗口
        self.show()
        
    def change_opacity(self, value):
        # 将滑块值转换为0.2到1.0之间的透明度
        opacity = value / 100.0
        self.setWindowOpacity(opacity)         
                
    
    def on_data_received(self, message):
        # 这里可以处理接收到的数据，例如更新界面显示
        # print(f"接收到数据: {message}")
        parts = message.split(',')
        timestamp = float(parts[0])
        pos_x = float(parts[1])
        pos_y = float(parts[2])
        pos_z = float(parts[3])
        heading = float(parts[4])
        # print("on_data_received heading:", heading)
        pitch = float(parts[5])
        bank = float(parts[6])
        lat = float(parts[7])
        long = float(parts[8])
        height = float(parts[9])
        self.plane_data={
            "heading": heading,
            "x": pos_x,
            "y": pos_y,
            "z": pos_z,
            "height": height
        }
        # print("heading:", self.plane_data['heading'])
        # print("on_data_received self update")
        self.update()  # 触发重画
        
    
    def startMission(self):
        # self.onDraw()  # 根据当前选择的索引重画
        print("startMission self update")
        self.update()  # 触发重画

        if not self.argsReady:
            # 输出dialog警告信息
            QMessageBox.warning(self, "参数未准备好", "请确保所有参数已准备好后再开始任务。")
            return
        if self.thread and self.thread.isRunning():
            print("Socket服务已经在运行中")
        else:
            # listening线程启动
            self.thread = QThread()
            self.worker = SocketWorker()
            self.worker.moveToThread(self.thread)
            self.worker.data_received.connect(self.on_data_received)  # 连接信号和槽函数
            self.thread.started.connect(self.worker.start_listening)
            self.thread.finished.connect(self.worker.stop_listening)
            self.thread.start()
        
        if Config["showEnemy"]:
            self.timer.start(timerTime)  # 启动计时器，每秒触发一次
            self.timerScreen.start(screenTime)
        if Config["showFriend"]:
            self.timerTeam.start(teamTime)  # 启动队友信息计时器
        if Config["isDefaultServer"]:
            serverInforDetail["serverIP"] = default_host
            serverInforDetail["serverPort"] = default_port
        else:
            serverInforDetail["serverIP"] = Config["serverIP"]
            serverInforDetail["serverPort"] = Config["serverPort"]
            
        self.startButton.setEnabled(False)  # 禁用开始按钮
        self.endButton.setEnabled(True)     # 启用结束按钮
        self.inforButton.setEnabled(False)  # 禁用信息输入按钮
        print(self.plane_data)
    
    def endMission(self):
                # """停止Socket服务"""
        if self.thread and self.thread.isRunning():
            # 停止worker
            self.worker.stop_listening()
            # 退出线程
            self.thread.quit()
            self.thread.wait()
            
            print("Socket服务已停止")
        else:
            print("Socket服务未运行")
        
        if Config["showEnemy"]:
            self.timer.stop()  # 停止计时器
            self.timerScreen.stop()  # 停止截图计时器
        if Config["showFriend"]:
            self.timerTeam.stop()  # 停止队友信息计时器
        self.screenShortList.clear()  # 清空截图列表
        self.startButton.setEnabled(True)   # 启用开始按钮
        self.endButton.setEnabled(False)    # 禁用结束按钮
        self.inforButton.setEnabled(True)   # 启用信息输入按钮
        print(self.plane_data)

        
    def showMetricsChanged(self, index):
        if index == 0:
            # 删除原有的选项并添加新的选项
            self.scaleComboBox.clear()
            self.scaleComboBox.addItems(['50km', '100km', '200km'])
            self.showMetrics = "km"
            Config["showMetrics"] = "km"
        elif index == 1:
            self.showMetrics = "nm"
            self.scaleComboBox.clear()
            self.scaleComboBox.addItems(['25nm', '50nm', '100nm'])
            Config["showMetrics"] = "nm"
        print("showMetricsChanged self update")
        self.update()  # 切换单位后重绘界面



    def showAndInputInfor(self):
        ## 希望显示出arsInputDialog，输入callSign和bullseye坐标
        ## 显示dialog, 界面继承arsInputDialog文件中的Ui_argsDialog
        # from arsInputDialog import UI_argsDialog
        # 如果当前文件夹存在AWACASConfig.txt文件，读取其中的内容并转换为字典，作为dialog中参数的默认设置
        # config_path 存在C盘用户下面的AppData\Local\AWACASConfig.txt文件
        
        
        config_path = get_config_path()

        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                config_str = f.read()
                try:
                    config_dict = eval(config_str)
                    if isinstance(config_dict, dict):
                        Config.update(config_dict)
                except Exception as e:
                    print("读取配置文件失败，使用默认配置。错误信息：", e)
        Config["id"] = program_id
        dialog = ArgsDialog(self)
        # dialog.setupUi(dialog)
        # dialog中参数默认设置
        dialog.callSignLineEdit.setText(Config["callSign"]["text"] + Config["callSign"]["num"])
        dialog.bullsEyeLat.setText(str(Config["bullseye"]["z"]))
        dialog.bullsEyeLong.setText(str(Config["bullseye"]["x"]))
        dialog.xEdit.setText(str(Config["screenShortRegion"]["x"]))
        dialog.yEdit.setText(str(Config["screenShortRegion"]["y"]))
        dialog.widthEdit.setText(str(Config["screenShortRegion"]["width"]))
        dialog.heightEdit.setText(str(Config["screenShortRegion"]["height"]))
        dialog.AWACASMARK_unit.addItems(['km', 'nm'])
        dialog.RemainTime.setText(str(Config["remainingTime"]))
        dialog.AWACASMARK_unit.setCurrentText(Config["awacsMetricUnit"])
        dialog.serverMode.addItems(['传统预警机', 'SPS服务器', 'BSC服务器'])
        dialog.serverMode.setCurrentIndex(Config["mode"])
        dialog.teamCodeEdit.setText(Config["teamcode"])
        dialog.serverHostEdit.setText(Config["serverIP"])
        dialog.portEdit.setText(str(Config["serverPort"]))
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            callSign = dialog.callSignLineEdit.text()
            if callSign == "abc9527" or Config["callSign"] == "":
                QMessageBox.warning(self, "输入错误", "请至少输入Callsign。")
                return
            # dialog.bullseyeLatLineEdit.text()输入限制为正负浮点数
            try:
                Config["callSign"]["text"] = ''.join(filter(str.isalpha, callSign))
                Config["callSign"]["num"] = ''.join(filter(str.isdigit, callSign))
                z = float(dialog.bullsEyeLat.text().strip())
                x = float(dialog.bullsEyeLong.text().strip())
                print(f"输入的坐标：X {x}, Z {z}")
                Config["bullseye"]["x"] = x
                Config["bullseye"]["z"] = z
                Config["screenShortRegion"]["x"] = int(dialog.xEdit.text())
                Config["screenShortRegion"]["y"] = int(dialog.yEdit.text())
                Config["screenShortRegion"]["width"] = int(dialog.widthEdit.text())
                Config["screenShortRegion"]["height"] = int(dialog.heightEdit.text())
                Config["awacsMetricUnit"] = dialog.AWACASMARK_unit.currentText()
                Config["remainingTime"] = int(dialog.RemainTime.text())
                Config["mode"] = dialog.serverMode.currentIndex()
                Config["teamcode"] = dialog.teamCodeEdit.text().strip()
                Config["serverIP"] = dialog.serverHostEdit.text().strip()
                Config["serverPort"] = int(dialog.portEdit.text().strip())
                
            except ValueError as e:
                QMessageBox.warning(self, "输入错误", str(e))
                return
            self.argsReady = True
            print("argsReady:", self.argsReady)
            print("Config:", Config)
            # 当前文件夹下生成一个AWACASConfig.txt文件，内容为Config字典的字符串表示
            with open(config_path, "w") as f:
                f.write(str(Config))
            
    def operateAwacsMark(self):
        # 检测self.thread是否存在且正在运行
        if not (self.thread and self.thread.isRunning()):
            print("udp服务未运行")
        
        if self.threadOCRFlask and self.threadOCRFlask.isRunning():
            print("Flask服务已经在运行中")
        else:
            self.threadOCRFlask = QThread()
            screenShortList_copy=self.screenShortList.copy()
            self.workerOCRFlask = operateAwacsMarkRemoteWorker(
                screenShortList_copy=screenShortList_copy,
                callSign=Config["callSign"],
                message_dic=self.message_dic.copy(),
                bullseye_dic=self.bullseye_dic.copy(),
                plane_data=self.plane_data.copy(),
                metric_unit=Config["awacsMetricUnit"],
                bullseye=Config["bullseye"].copy()
            )
            self.workerOCRFlask.moveToThread(self.threadOCRFlask)
            self.workerOCRFlask.data_received.connect(self.on_data_received_flask)  # 连接信号和槽函数
            self.threadOCRFlask.started.connect(self.workerOCRFlask.start_working)
            self.threadOCRFlask.finished.connect(self.workerOCRFlask.stop_working)
            self.threadOCRFlask.start()
        # self.update()  # 刷新界面显示
    
    def operateTeamMate(self):
        if not (self.thread and self.thread.isRunning()):
            print("udp服务未运行")
        if self.threadTeamFlask and self.threadTeamFlask.isRunning():
            print("队友标记Flask服务已经在运行中")
        else:
            self.threadTeamFlask = QThread()
            self.workerTeamFlask = operateTeamMateMarkRemoteWorker(
                plane_data=self.plane_data.copy(),
            )
            self.workerTeamFlask.moveToThread(self.threadTeamFlask)
            self.workerTeamFlask.data_received.connect(self.on_data_received_team)  # 连接信号和槽函数
            self.threadTeamFlask.started.connect(self.workerTeamFlask.start_working)
            self.threadTeamFlask.finished.connect(self.workerTeamFlask.stop_working)
            self.threadTeamFlask.start()
    
    def on_data_received_flask(self, message_dicANDbullseye_dic):
        message_dic, bullseye_dic = message_dicANDbullseye_dic
        self.message_dic = message_dic
        self.bullseye_dic = bullseye_dic
        # print("on_data_received_flask self update")
        self.threadOCRFlask.quit()
        self.workerOCRFlask.stop_working()
        self.update()  # 刷新界面显示
        
    def on_data_received_team(self, team_members):
        if not team_members:
            print("未接收到队友数据")
        else:
            self.team_members = team_members
        self.threadTeamFlask.quit()
        self.workerTeamFlask.stop_working()
        self.update()  # 刷新界面显示
        
    def takeScreenShotTimer(self):
        # 这里可以添加需要定时执行的操作，例如刷新界面、更新数据等
        if len(self.screenShortList) >= 2:
            return
        self.screenShortList.clear()  # 清空列表以准备下一轮截图
        print("执行定时任务：截图， 截图数量：", len(self.screenShortList))
        # 记录截图和时间戳
        self.screenShortList.append(take_screenshot(Config["screenShortRegion"]["x"], Config["screenShortRegion"]["y"], 
                                                    Config["screenShortRegion"]["width"], 
                                                    Config["screenShortRegion"]["height"])
        )

def check_expiration():
    timerTime = 2000  # 计时器时间间隔，单位为毫秒
    screenTime = 800  # 截图计时器时间间隔，单位为毫秒
    teamTime = 4000  # 队伍信息计时器时间间隔，单位为毫秒
    # 设置过期日期
    expire_date = datetime.date(2026, 5, 20)
    current_date = datetime.date.today()
    
    if current_date > expire_date:
        # 创建 QApplication 实例（必需）
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        # 创建弹窗
        msg_box = QMessageBox()
        msg_box.setWindowTitle("软件已过期")
        msg_box.setText("软件已过期，请联系开发者获取新版")
        msg_box.setIcon(QMessageBox.Icon.Critical)
        msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg_box.setDefaultButton(QMessageBox.StandardButton.Ok)
        
        # 显示弹窗并等待用户点击
        msg_box.exec()
        
        # 退出程序
        sys.exit(1)

if __name__ == "__main__":
    # check_expiration()
    app = QApplication(sys.argv)
    form = Winform()
    form.show()
    sys.exit(app.exec())
