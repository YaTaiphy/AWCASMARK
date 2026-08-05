import math
import os
import sys
from PySide6.QtCore import Qt, QPoint, QPointF
from PySide6.QtGui import QPen, QColor, QPolygonF, QFont
import http.client
from AWACASMARK_config import Config
import time

timeColor = {
    0: QColor(0, 0, 51),
    1: QColor(0, 0, 51, 127),
    2: QColor(0, 0, 153, 127),
    3: QColor(0, 0, 255, 127),
    4: QColor(102, 102, 255, 127),
    5: QColor(102, 102, 255, 64),
    6: QColor(102, 102, 255, 32),
    7: QColor(102, 102, 255, 16),
}

friendsColor = QColor(255, 128, 0, 160)

def serverIsReachable(server_ip, server_port, timeout=6):
    try:
        conn = http.client.HTTPConnection(server_ip, server_port, timeout=timeout)
        # 服务器get路径为/health
        # @app.route('/health', methods=['GET'])
        # def health_check():
        #     return jsonify({'status': 'Flask server is running'})
        
        conn.request("GET", "/health")
        response = conn.getresponse()
        if response.status == 200:
            return True
        else:
            return False
    except Exception as e:
        print(f"无法连接到服务器 {server_ip}:{server_port} - {e}")
        return False

def drawFriendPlaneByBearingAndDistanceAbsScale(painter, center_x, center_y, plane_data, team_members ,
                                               scale, radius_interval, max_radius):
    if not team_members:
        return
    for member in team_members:
        if int(time.time()) - member['timestamp'] > Config["showFriendTime"]:
            continue  # 超过显示时间，不绘制
        
        painter.setBrush(friendsColor)  # 填充橙色
        distance, bearing = calculate_bearing_and_distance(plane_data['x'], plane_data['z'], 
                                                           member['x'], member['z'])
        if Config["showMetrics"] == "nm":
            distance /= 1852  # 将米转换为海里
            height = member['y'] / 1000 * 3.28084  # 将米转换为千英尺
            if distance > scale:
                continue  # 超出最大显示范围，不绘制
        else:
            distance /= 1000  # 将米转换为公里
            height = member['y'] / 1000 # 高度千米
            if distance > scale:
                continue  # 超出最大显示范围，不绘制
        direction_angle = bearing + 90  # 方向角度（0度向右，90度向上，180度向左，270度向下）
        # 将角度转换为弧度
        angle_rad = math.radians(direction_angle)
        
        # 计算距离像素
        distance_pixels = (distance / scale) * max_radius
        # 计算需要绘制的中心点
        enemy_center_x = center_x - distance_pixels * math.cos(angle_rad)
        enemy_center_y = center_y - distance_pixels * math.sin(angle_rad)  # Y轴向下为正，所以减号
        
        # 可选：添加一个中心点标记
        pen = QPen()
        pen.setStyle(Qt.SolidLine)
        pen.setColor(friendsColor)
        painter.setPen(pen)
        painter.drawEllipse(QPoint(enemy_center_x, enemy_center_y), 3, 3)
        # 标记点右上方显示高度，高度保留一位小数
        font = QFont()
        font.setPointSize(8)
        painter.setFont(font)
        painter.drawText(enemy_center_x + 6, enemy_center_y - 3, f"{height:.1f}")
        
        callsign = member["callSign"]
        painter.drawText(enemy_center_x + 6, enemy_center_y + 6, f"{callsign}")
        
        angle_rad = math.radians((member["heading"] + 90)%360)
        # 添加箭头表示前进方向
        arrow_length = max_radius/20  # 箭头长度
        

                    # 计算箭头终点（头部）
        arrow_end_x = enemy_center_x - arrow_length * math.cos(angle_rad)
        arrow_end_y = enemy_center_y - arrow_length * math.sin(angle_rad)  # Y轴向下为正，所以减号

        # 绘制箭头线
        pen.setColor(friendsColor)
        pen.setWidth(2)
        painter.setPen(pen)
        painter.drawLine(enemy_center_x, enemy_center_y, arrow_end_x, arrow_end_y)

        # 绘制箭头头部（三角形）
        arrow_head_size = radius_interval/20  # 箭头头部大小
        arrow_angle = math.radians(30)  # 箭头张开角度

        # 计算箭头头部的两个点
        angle1 = angle_rad + arrow_angle
        angle2 = angle_rad - arrow_angle

        point1_x = arrow_end_x + arrow_head_size * math.cos(angle1)
        point1_y = arrow_end_y - arrow_head_size * math.sin(angle1)

        point2_x = arrow_end_x + arrow_head_size * math.cos(angle2)
        point2_y = arrow_end_y - arrow_head_size * math.sin(angle2)

        # 绘制箭头头部三角形
        arrow_head = QPolygonF([
            QPointF(arrow_end_x, arrow_end_y),
            QPointF(point1_x, point1_y),
            QPointF(point2_x, point2_y)
        ])
        painter.drawPolygon(arrow_head)
        painter.setBrush(QColor(0, 0, 255))  # 填充蓝色
    
def drawFriendPlaneByBearingAndDistanceSAScale(painter, center_x, center_y, plane_data, team_members ,
                                               scale, radius_interval, max_radius):
    if not team_members:
        return
    
    for member in team_members:
        if int(time.time()) - member['timestamp'] > Config["showFriendTime"]:
            continue  # 超过显示时间，不绘制
        
        painter.setBrush(friendsColor)  # 填充橙色
        distance, bearing = calculate_bearing_and_distance(plane_data['x'], plane_data['z'], 
                                                           member['x'], member['z'])
        # print(f"计算得到的距离: {distance} 米, 方位角: {bearing} 度")
        if Config["showMetrics"] == "nm":
            distance /= 1852  # 将米转换为海里
            height = member['y'] / 1000 * 3.28084  # 将米转换为千英尺
            if distance > scale:
                continue  # 超出最大显示范围，不绘制
        else:
            distance /= 1000  # 将米转换为公里
            height = member['y'] / 1000 # 高度千米
            if distance > scale:
                continue  # 超出最大显示范围，不绘制
        direction_angle = bearing + 90 - plane_data['heading']  # 方向角度（0度向右，90度向上，180度向左，270度向下）
        # 将角度转换为弧度
        angle_rad = math.radians(direction_angle)
        
        # 计算距离像素
        distance_pixels = (distance / scale) * max_radius
        # 计算需要绘制的中心点
        enemy_center_x = center_x - distance_pixels * math.cos(angle_rad)
        enemy_center_y = center_y - distance_pixels * math.sin(angle_rad)  # Y轴向下为正，所以减号
        
        # 可选：添加一个中心点标记
        pen = QPen()
        pen.setStyle(Qt.SolidLine)
        pen.setColor(friendsColor)
        painter.setPen(pen)
        painter.drawEllipse(QPoint(enemy_center_x, enemy_center_y), 3, 3)
        # 标记点右上方显示高度，高度保留一位小数
        font = QFont()
        font.setPointSize(8)
        painter.setFont(font)
        painter.drawText(enemy_center_x + 6, enemy_center_y - 3, f"{height:.1f}")
        
        callsign = member["callSign"]
        painter.drawText(enemy_center_x + 6, enemy_center_y + 6, f"{callsign}")
        
        angle_rad = math.radians((member["heading"] + 90 - plane_data['heading'])%360)
        # 添加箭头表示前进方向
        arrow_length = max_radius/20  # 箭头长度
        

                    # 计算箭头终点（头部）
        arrow_end_x = enemy_center_x - arrow_length * math.cos(angle_rad)
        arrow_end_y = enemy_center_y - arrow_length * math.sin(angle_rad)  # Y轴向下为正，所以减号

        # 绘制箭头线
        pen.setColor(friendsColor)
        pen.setWidth(2)
        painter.setPen(pen)
        painter.drawLine(enemy_center_x, enemy_center_y, arrow_end_x, arrow_end_y)

        # 绘制箭头头部（三角形）
        arrow_head_size = radius_interval/20  # 箭头头部大小
        arrow_angle = math.radians(30)  # 箭头张开角度

        # 计算箭头头部的两个点
        angle1 = angle_rad + arrow_angle
        angle2 = angle_rad - arrow_angle

        point1_x = arrow_end_x + arrow_head_size * math.cos(angle1)
        point1_y = arrow_end_y - arrow_head_size * math.sin(angle1)

        point2_x = arrow_end_x + arrow_head_size * math.cos(angle2)
        point2_y = arrow_end_y - arrow_head_size * math.sin(angle2)

        # 绘制箭头头部三角形
        arrow_head = QPolygonF([
            QPointF(arrow_end_x, arrow_end_y),
            QPointF(point1_x, point1_y),
            QPointF(point2_x, point2_y)
        ])
        painter.drawPolygon(arrow_head)
        painter.setBrush(QColor(0, 0, 255))  # 填充蓝色

def drawEnemyPlaneByBearingAndDistanceAbsScale(painter, center_x, center_y,  
                                               bearing_deg, distance, message, height, scale, 
                                               radius_interval,max_radius, timeElapse, friend = False):
    painter.setBrush(timeColor[timeElapse])  # 设置填充颜色
    # 距离
    enemy_heading = message["enemy_heading"]
    condition = message["condition"]
    
    if distance > scale:
        return  # 超出最大显示范围，不绘制
    direction_angle = bearing_deg + 90  # 方向角度（0度向右，90度向上，180度向左，270度向下）
    # 将角度转换为弧度
    angle_rad = math.radians(direction_angle)
    
    # 计算距离像素
    distance_pixels = (distance / scale) * max_radius
    # 计算需要绘制的中心点
    enemy_center_x = center_x - distance_pixels * math.cos(angle_rad)
    enemy_center_y = center_y - distance_pixels * math.sin(angle_rad)  # Y轴向下为正，所以减号
    
    # 可选：添加一个中心点标记
    pen = QPen()
    pen.setStyle(Qt.SolidLine)
    pen.setColor(timeColor[timeElapse])  
    painter.setPen(pen)
    painter.drawEllipse(QPoint(enemy_center_x, enemy_center_y), 3, 3)
    # 标记点右上方显示高度，高度保留一位小数
    font = QFont()
    font.setPointSize(8)
    painter.setFont(font)
    painter.drawText(enemy_center_x + 6, enemy_center_y - 3, f"{height:.1f}")
    
        # 如果为sps模式
    if Config["mode"] == 1:
        # 绘制马赫数
        mach_speed = message["speed"]
        painter.drawText(enemy_center_x + 6, enemy_center_y + 6, f"M{mach_speed:.2f}")
        # 绘制敌机代号
        callsign = message["callsign"]
        painter.drawText(enemy_center_x + 6, enemy_center_y - 12, f"{callsign}")
    
    elif Config["mode"] == 3:
        callsign = message["callsign"]
        painter.drawText(enemy_center_x + 6, enemy_center_y - 12, f"{callsign}")
    
    
    if enemy_heading <0:
        return
    
    angle_rad = math.radians((enemy_heading + 90)%360)
    # 添加箭头表示前进方向
    arrow_length = max_radius/20  # 箭头长度
    

                # 计算箭头终点（头部）
    arrow_end_x = enemy_center_x - arrow_length * math.cos(angle_rad)
    arrow_end_y = enemy_center_y - arrow_length * math.sin(angle_rad)  # Y轴向下为正，所以减号

    # 绘制箭头线
    pen.setColor(timeColor[timeElapse])  
    pen.setWidth(2)
    painter.setPen(pen)
    if condition == 0:
        painter.drawLine(enemy_center_x - arrow_length * math.cos(angle_rad), 
                         enemy_center_y + arrow_length * math.sin(angle_rad), 
                         arrow_end_x, arrow_end_y)
    else:
        painter.drawLine(enemy_center_x, enemy_center_y, arrow_end_x, arrow_end_y)

    # 绘制箭头头部（三角形）
    arrow_head_size = radius_interval/20  # 箭头头部大小
    arrow_angle = math.radians(30)  # 箭头张开角度

    # 计算箭头头部的两个点
    angle1 = angle_rad + arrow_angle
    angle2 = angle_rad - arrow_angle

    point1_x = arrow_end_x + arrow_head_size * math.cos(angle1)
    point1_y = arrow_end_y - arrow_head_size * math.sin(angle1)

    point2_x = arrow_end_x + arrow_head_size * math.cos(angle2)
    point2_y = arrow_end_y - arrow_head_size * math.sin(angle2)

    # 绘制箭头头部三角形
    arrow_head = QPolygonF([
        QPointF(arrow_end_x, arrow_end_y),
        QPointF(point1_x, point1_y),
        QPointF(point2_x, point2_y)
    ])
    painter.drawPolygon(arrow_head)
    painter.setBrush(QColor(0, 0, 255))  # 填充蓝色
    
    
def drawEnemyPlaneByBearingAndDistanceSAScale(painter, center_x, center_y,  heading,
                                               bearing_deg, distance, message,
                                               height, scale, radius_interval,max_radius, timeElapse, friend = False):
    # 距离
    enemy_heading = message["enemy_heading"]
    condition = message["condition"]
    if distance > scale:
        return  # 超出最大显示范围，不绘制
    direction_angle = bearing_deg + 90 - heading # 方向角度（0度向右，90度向上，180度向左，270度向下）
    # 将角度转换为弧度
    angle_rad = math.radians(direction_angle)
    
    # 计算距离像素
    distance_pixels = (distance / scale) * max_radius
    # 计算需要绘制的中心点
    enemy_center_x = center_x - distance_pixels * math.cos(angle_rad)
    enemy_center_y = center_y - distance_pixels * math.sin(angle_rad)  # Y轴向下为正，所以减号
    
    # 可选：添加一个中心点标记
    pen = QPen()
    pen.setStyle(Qt.SolidLine)
    pen.setColor(timeColor[timeElapse])  
    painter.setPen(pen)
    painter.drawEllipse(QPoint(enemy_center_x, enemy_center_y), 3, 3)
    # 标记点右上方显示高度
    font = QFont()
    font.setPointSize(6)
    painter.setFont(font)
    painter.drawText(enemy_center_x + 6, enemy_center_y - 3, f"{height:.1f}")
    
    
    # 如果为sps模式
    if Config["mode"] == 1:
        # 绘制马赫数
        mach_speed = message["speed"]
        painter.drawText(enemy_center_x + 6, enemy_center_y + 6, f"M{mach_speed:.2f}")
        # 绘制敌机代号
        callsign = message["callsign"]
        painter.drawText(enemy_center_x + 6, enemy_center_y - 12, f"{callsign}")
    elif Config["mode"] == 2:
        callsign = message["callsign"]
        painter.drawText(enemy_center_x + 6, enemy_center_y - 12, f"{callsign}")
    
    if enemy_heading <0:
        return
    
    angle_rad = math.radians(enemy_heading + 90 - heading)
    # 添加箭头表示前进方向
    arrow_length = max_radius/20  # 箭头长度
    
 # 计算箭头终点（头部）
    arrow_end_x = enemy_center_x - arrow_length * math.cos(angle_rad)
    arrow_end_y = enemy_center_y - arrow_length * math.sin(angle_rad)  # Y轴向下为正，所以减号

    # 绘制箭头线
    pen.setColor(timeColor[timeElapse])  
    pen.setWidth(2)
    painter.setPen(pen)
    if condition == 0:
        painter.drawLine(enemy_center_x - arrow_length * math.cos(angle_rad), 
                         enemy_center_y + arrow_length * math.sin(angle_rad), 
                         arrow_end_x, arrow_end_y)
    else:
        painter.drawLine(enemy_center_x, enemy_center_y, arrow_end_x, arrow_end_y)

    # 绘制箭头头部（三角形）
    arrow_head_size = radius_interval/20  # 箭头头部大小
    arrow_angle = math.radians(30)  # 箭头张开角度

    # 计算箭头头部的两个点
    angle1 = angle_rad + arrow_angle
    angle2 = angle_rad - arrow_angle

    point1_x = arrow_end_x + arrow_head_size * math.cos(angle1)
    point1_y = arrow_end_y - arrow_head_size * math.sin(angle1)

    point2_x = arrow_end_x + arrow_head_size * math.cos(angle2)
    point2_y = arrow_end_y - arrow_head_size * math.sin(angle2)

    # 绘制箭头头部三角形
    arrow_head = QPolygonF([
        QPointF(arrow_end_x, arrow_end_y),
        QPointF(point1_x, point1_y),
        QPointF(point2_x, point2_y)
    ])
    painter.drawPolygon(arrow_head)
    painter.setBrush(QColor(0, 0, 255))  # 填充蓝色
    
    
# from geopy.distance import distance
# from geopy.distance import geodesic
# from geopy import Point
def offset_coordinate(x, z, distance_m, bearing_deg):
    """
    在DCS平面坐标系中，根据起始点、距离和方位角计算偏移后的坐标
    
    参数:
        x: 起始X坐标（北向，米）
        z: 起始Z坐标（东向，米）
        distance_m: 偏移距离（米）
        bearing_deg: 方位角（度，0°=北，90°=东，180°=南，270°=西）
    
    返回:
        (new_x, new_z): 偏移后的坐标（米）
    """
    # 方位角转换为弧度
    bearing_rad = math.radians(bearing_deg)
    
    # 平面三角计算偏移量
    # X轴向北（0°方向）
    dx = distance_m * math.cos(bearing_rad)
    # Z轴向东（90°方向）
    dz = distance_m * math.sin(bearing_rad)
    
    # 新坐标
    new_x = x + dx
    new_z = z + dz
    
    return new_x, new_z
    # """
    # 根据起始点、距离和方位角计算偏移后的经纬度（球面近似）
    
    # 参数:
    #     lat: 起始纬度（十进制度数）
    #     lon: 起始经度（十进制度数）
    #     distance_m: 偏移距离（米）
    #     bearing_deg: 方位角（度，0=北，90=东，180=南，270=西）
    
    # 返回:
    #     (new_lat, new_lon): 偏移后的经纬度（十进制度数）
    # """
    # R = 6371000  # 地球平均半径（米）
    
    # # 转换为弧度
    # lat_rad = math.radians(lat)
    # lon_rad = math.radians(lon)
    # bearing_rad = math.radians(bearing_deg)
    
    # # 角距离（弧度）
    # angular_distance = distance_m / R
    
    # # 球面三角公式
    # new_lat_rad = math.asin(
    #     math.sin(lat_rad) * math.cos(angular_distance) +
    #     math.cos(lat_rad) * math.sin(angular_distance) * math.cos(bearing_rad)
    # )
    
    # new_lon_rad = lon_rad + math.atan2(
    #     math.sin(bearing_rad) * math.sin(angular_distance) * math.cos(lat_rad),
    #     math.cos(angular_distance) - math.sin(lat_rad) * math.sin(new_lat_rad)
    # )
    
    # # 转换回度数
    # new_lat = math.degrees(new_lat_rad)
    # new_lon = math.degrees(new_lon_rad)
    
    # return new_lat, new_lon
    # """
    # 使用geopy计算偏移坐标（基于椭球体）
    # """
    
    # origin = Point(lat, lon)
    # # distance() 接受 (距离, 单位)
    # destination = distance(meters=distance_m).destination(origin, bearing_deg)
    
    # return destination.latitude, destination.longitude

def calculate_bearing_and_distance(x1, z1, x2, z2):
    """
    在DCS平面坐标系中，计算B点相对于A点的距离和方位角
    
    参数:
        x1, z1: A点坐标（北向，东向，米）
        x2, z2: B点坐标（北向，东向，米）
    
    返回:
        distance_m: 距离（米）
        bearing_deg: 方位角（度，0°=北，90°=东，180°=南，270°=西）
    """
    # 计算差值
    dx = x2 - x1  # 北向差值
    dz = z2 - z1  # 东向差值
    
    # 距离（勾股定理）
    distance_m = math.sqrt(dx * dx + dz * dz)
    
    # 方位角（atan2使用 dz, dx）
    # atan2(y, x) 返回从X轴正方向逆时针的角度
    # 这里 X轴=北，Y轴=东，所以使用 atan2(dz, dx)
    bearing_rad = math.atan2(dz, dx)
    bearing_deg = math.degrees(bearing_rad)
    
    # 归一化到 0-360 度
    bearing_deg = (bearing_deg + 360) % 360
    
    return distance_m, bearing_deg
    # """
    # 使用geopy计算距离和方位角
    # """
    # p1 = Point(lat1, lon1)
    # p2 = Point(lat2, lon2)
    
    # # 距离
    # distance_m = geodesic(p1, p2).meters
    
    # # 方位角（使用公式计算）
    # lat1_rad = math.radians(lat1)
    # lon1_rad = math.radians(lon1)
    # lat2_rad = math.radians(lat2)
    # lon2_rad = math.radians(lon2)
    
    # dlon = lon2_rad - lon1_rad
    # x = math.sin(dlon) * math.cos(lat2_rad)
    # y = math.cos(lat1_rad) * math.sin(lat2_rad) - math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(dlon)
    # bearing_rad = math.atan2(x, y)
    # bearing_deg = math.degrees(bearing_rad)
    # bearing_deg = (bearing_deg + 360) % 360
    
    # return distance_m, bearing_deg
    
    # """
    # 计算B点相对于A点的方位角和距离（球面近似）
    
    # 参数:
    #     lat1, lon1: A点坐标（十进制度数）
    #     lat2, lon2: B点坐标（十进制度数）
    
    # 返回:
    #     distance_m: 距离（米）
    #     bearing_deg: 方位角（度，0=北，90=东，180=南，270=西）
    # """
    # R = 6371000  # 地球平均半径（米）
    
    # # 转换为弧度
    # lat1_rad = math.radians(lat1)
    # lon1_rad = math.radians(lon1)
    # lat2_rad = math.radians(lat2)
    # lon2_rad = math.radians(lon2)
    
    # # 差值
    # dlat = lat2_rad - lat1_rad
    # dlon = lon2_rad - lon1_rad
    
    # # Haversine公式计算距离
    # a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
    # c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    # distance_m = R * c
    
    # # 计算方位角
    # y = math.sin(dlon) * math.cos(lat2_rad)
    # x = math.cos(lat1_rad) * math.sin(lat2_rad) - math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(dlon)
    # bearing_rad = math.atan2(y, x)
    # bearing_deg = math.degrees(bearing_rad)
    
    # # 归一化到0-360度
    # bearing_deg = (bearing_deg + 360) % 360
    
    # return distance_m, bearing_deg
    
def bullsEyeCaculation(bullseye_lat, bullseye_long, 
                       enemy_bearing, enemy_distance, 
                       plane_lat, plane_long, metric_unit):
    if metric_unit == "nm":
        enemy_distance *= 1852  # 将海里转换为米
    else:
        enemy_distance *= 1000  # 将公里转换为米
    # 计算敌机相对于牛眼的经纬度
    enemy_lat, enemy_long = offset_coordinate(bullseye_lat, bullseye_long, enemy_distance, enemy_bearing)
    # 计算敌机相对于牛眼的方位角和距离
    distance_to_enemy, bearing_to_enemy = calculate_bearing_and_distance(plane_lat, plane_long, enemy_lat, enemy_long)
    if metric_unit == "nm":
        distance_to_enemy /= 1852  # 将米转换为海里
    else:
        distance_to_enemy /= 1000  # 将米转换为公里
    return distance_to_enemy, bearing_to_enemy



def dm_to_dd(degrees, minutes):
    """
    将度分格式转换为十进制度
    """
    return degrees + minutes / 60

def parse_dm_coordinate(coord_str):
    """
    解析类似 "N 42°10.659'" 或 "E 42°28.853'" 的坐标字符串
    返回 (方向, 度, 分)
    """
    # 去除空格
    coord_str = coord_str.strip()
    
    # 提取方向（N/S/E/W）
    direction = coord_str[0]
    
    # 提取数字部分
    # 格式：方向 + 空格 + 度数 + ° + 分数 + '
    import re
    match = re.search(r'(\d+)°(\d+\.\d+)\'', coord_str)
    if match:
        degrees = float(match.group(1))
        minutes = float(match.group(2))
        return direction, degrees, minutes
    else:
        raise ValueError(f"无法解析坐标格式: {coord_str}")

def convert_to_decimal(coord_str):
    """
    将度分格式坐标转换为十进制度字符串
    """
    direction, degrees, minutes = parse_dm_coordinate(coord_str)
    decimal_value = dm_to_dd(degrees, minutes)
    
    # 根据方向确定正负值（S和W为负）
    if direction in ['S', 'W']:
        decimal_value = -decimal_value
    
    return decimal_value

def format_as_numeric(decimal_value, decimals=4):
    """
    格式化为类似 44.9666 的数字格式
    """
    return f"{decimal_value:.{decimals}f}"

def number_mistake_correction(text):
    """
    对常见的数字识别错误进行纠正
    """
    corrected_text = text.replace("o", "0").replace("O", "0").replace("c", "0")\
                    .replace("l", "1").replace("I", "1").replace("i", "1")\
                    .replace("b", "6").replace("g", "9").replace("s", "5")\
                    .replace("S", "5").replace("z", "2").replace("Z", "2")\
                    .replace("q", "9").replace("Q", "9").replace("L", "1")\
                    .replace("L", "1").replace("B", "8").replace("G", "6").replace("T", "7").replace("t", "7")\
                    .replace("/", "1").replace("\\", "1")
    
    return corrected_text

def alphabet_mistacke_correction(text):
    """
    对常见的字母识别错误进行纠正
    """
    corrected_text = text.replace("0", "O").replace("8", "B").replace("6", "G").replace("9", "Q").replace("5", "S")\
                    .replace("1", "I").replace("2", "Z").replace("4", "A").replace("7", "T").replace("3", "E")
    return corrected_text

def get_config_path():
    """获取配置文件的完整路径（保存在 %LOCALAPPDATA% 目录）"""
    # 获取 LOCALAPPDATA 环境变量
    local_app_data = os.environ.get('LOCALAPPDATA')
    
    if local_app_data is None:
        # 备用方案：手动构建路径
        local_app_data = os.path.join(os.environ['USERPROFILE'], 'AppData', 'Local')
    
    # 返回配置文件完整路径
    return os.path.join(local_app_data, "AWACASConfig.txt")

if __name__ == "__main__":
    # lat_str = "N 42°10.659'"
    # lon_str = "E 42°28.853'"
    
    # # 转换为十进制度
    # lat_decimal = convert_to_decimal(lat_str)
    # lon_decimal = convert_to_decimal(lon_str)
    
    # print(f"十进制度坐标: 纬度={lat_decimal}, 经度={lon_decimal}")
    
    # # 42.52216118277683, 'long': 42.089863159203816,
    # # print(parse_dm_coordinate("N42.52216118277683"))
    # # print(parse_dm_coordinate("E42.089863159203816"))
    
    
    
    # lat = -61910 
    # long = +18406
    # distance_m = 579000
    # bearing_deg = 118
    
    # new_lat, new_long = offset_coordinate(lat, long, distance_m, bearing_deg)
    # print(f"偏移后的坐标: 纬度={new_lat:.6f}, 经度={new_long:.6f}")
    # distance, bearing = calculate_bearing_and_distance(lat, long, new_lat, new_long)
    # print(f"计算的距离: {distance:.2f} 米, 方位角: {bearing:.2f} 度")
    import re
    from time import time
    key_callsign = {"text": "Springfield", "num": "11"}
    metric_unit = "nm"
    bullseye_x, bullseye_z = 0, 0
    plane_x, plane_z = 10000, 10000
    message_dic = {}
    bullseye_dic = {}
    # ['预警机（MagicL-L): Springfield 11,Magicl-1，敌情（BRA),097方位，距离120，高度 5000，迎头', '预学机（Oyerlordl-l): Springield 1L, Oyerlordl-1，突现的敌方机队，097.方位，距离,90，高度 6000，迎头']
    text = ["须警机（MagicL-L): Springield LL, Magic'-l，敌情（BRA)，09/方位，距离120，高度5000，迎头", '预警机（Oyerlordl-l): Springfield LL, Overlordl-l，突现的敌方机队，097·方位，距离90，高度6000，迎头']
    for t in text:
        parts = t.replace("，", ",").replace("：",":").replace(".", ",").\
            replace("。", ",").replace("、", ",").replace(";",",").split(",")
        print("============================")
        print("识别的文字：", t)
        need_words = ["方","位置","距","离","高","度"]
        if len(parts) == 7 and ("方" in t or "位" in t):
            if key_callsign["text"] == "":
                ocr_callsign = number_mistake_correction(parts[0].split(":")[-1].strip())
                if key_callsign["num"] != ocr_callsign:
                    continue
            else:
                ocr_callsign = parts[0].split(":")[-1].strip()
                ocr_callsign_num = number_mistake_correction(ocr_callsign[-len(key_callsign["num"]):])
                # test
                print(f"识别的callsign: {ocr_callsign}")
                if key_callsign["num"] != ocr_callsign_num:
                    continue
                ocr_callsign_first = alphabet_mistacke_correction(ocr_callsign[0]).lower()
                print(f"识别的callsign首字母: {ocr_callsign_first}")
                key_callsign_first = key_callsign["text"][0].lower()
                if key_callsign_first != ocr_callsign_first:
                    continue
            
            # split with , and ，get last 4 part
                # map "头" 1， "追" 2， "侧" 3
            if "头" or "迎" in parts[-1]:
                condition = 1
            elif "追" or "尾" in parts[-1]:
                condition = -1
            elif "侧" or "对" in parts[-1]:
                condition = 0
            else:
                condition = -2  # 未识别到明确的方位关系，设为-2
            
            enemy_altitude = int(''.join(re.findall(r'\d+', "0" + number_mistake_correction(parts[-2]))))
            enemy_distance = int(''.join(re.findall(r'\d+', "0" + number_mistake_correction(parts[-3]))))
            print("=============================")
            # print("距离: ", enemy_distance,)
            if metric_unit == "nm":
                enemy_distance = int(enemy_distance * 1852)
            else:
                enemy_distance = int(enemy_distance * 1000)
            
            enemy_bearing = int(''.join(re.findall(r'\d+', "0" + number_mistake_correction(parts[-4]))))
            if condition == 1:  
                enemy_heading = (enemy_bearing + 180) % 360
            elif condition == -1:  
                enemy_heading = enemy_bearing
            elif condition == 0:
                enemy_heading = (enemy_bearing + 90) % 360
            else:
                enemy_heading = -1  # 未识别到明确的方位关系，设为-1

            formatted_message = int(enemy_altitude + enemy_distance + enemy_bearing + enemy_heading + condition)
            
            get_time = int(time())
            
            
            if formatted_message not in message_dic:
                new_x, new_y = offset_coordinate(plane_x, plane_z, enemy_distance, enemy_bearing)
                
                message_dic[formatted_message] = {"timeStamp": get_time, 
                                                    "enemy_altitude": enemy_altitude, 
                                                    "enemy_heading": enemy_heading,
                                                    "x": new_x,
                                                "z": new_y,
                                                "condition": condition
                                                    }
                # print("新消息：", formatted_message) 
                # print("方位: ", enemy_bearing, "高度: ", enemy_altitude)
        elif len(parts) == 3 and ("机" in parts[0] or "队" in parts[0]) and any(word in t for word in need_words):
            bulls_enemy_altitude = int(''.join(re.findall(r'\d+', "0" + number_mistake_correction(parts[-1]))))
            
            bulls_enemy_distance = int(''.join(re.findall(r'\d+', "0" + number_mistake_correction(parts[-2]))))
            if metric_unit == "nm":
                bulls_enemy_distance = int(bulls_enemy_distance * 1852)
            else:
                bulls_enemy_distance = int(bulls_enemy_distance * 1000)
            bulls_enemy_bearing = int(''.join(re.findall(r'\d+', "0" + number_mistake_correction(parts[-3]))))
            
            formatted_message = int(bulls_enemy_altitude + bulls_enemy_distance + bulls_enemy_bearing)
            
            get_time = int(time())
            
            if formatted_message not in bullseye_dic:
                new_x, new_y = offset_coordinate(bullseye_x, bullseye_z, 
                                                bulls_enemy_distance, bulls_enemy_bearing)
                bullseye_dic[formatted_message] = {"timeStamp": get_time,
                                                    "bulls_enemy_altitude": bulls_enemy_altitude,
                                                    "x": new_x,
                                                    "z": new_y,
                                                    "enenmy_heading": -1
                                                    }
                print("新牛眼消息：", formatted_message) 
    
    