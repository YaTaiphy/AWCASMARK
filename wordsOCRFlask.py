from time import sleep, time
from PIL import Image, ImageEnhance
from mss import mss
import numpy as np
from time import sleep
import re
import json
import io
import base64
import http.client

from serverInfor import serverInforDetail
from utils import alphabet_mistacke_correction, number_mistake_correction, offset_coordinate

nm_feature = ["nm", "feet"]
km_feature = ["km", "m"]

condition_feature = ["hot", "cold", "flank", "beam"]

from AWACASMARK_config import Config

def take_screenshot(x, y, width, height):
    with mss() as sct:
        region = {
            "top": y,
            "left": x,
            "width": width,
            "height": height
        }
        screenshot = sct.grab(region)
        img = Image.frombytes('RGB', (screenshot.width, screenshot.height), screenshot.rgb)
        # img转化为灰度图，测试表明灰度图效果变差，可能是因为某些文字颜色较浅，转化为灰度图后对比度降低导致识别效果变差
        # img = img.convert('L')
        # 图像降低亮度，提高对比度
        # enhancer = ImageEnhance.Brightness(img)
        # img = enhancer.enhance(0.5)  # 降低亮度
        # enhancer = ImageEnhance.Contrast(img)
        # img = enhancer.enhance(2)  # 提高对比度
        return img
    
def image_to_base64(image):
    """将PIL图像转换为base64字符串"""
    # 将图像保存到内存中的字节流
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    buffer.seek(0)
    
    # 编码为base64
    image_base64 = base64.b64encode(buffer.read()).decode('utf-8')
    return image_base64


def send_image_to_server(mode, image, server_ip=serverInforDetail["serverIP"], server_port=serverInforDetail["serverPort"]):
    """发送图像到Flask服务器"""
    try:
        # 准备连接
        conn = http.client.HTTPConnection(server_ip, server_port, timeout=10)
        
        # 准备请求数据
        image_base64 = image_to_base64(image)
        data = {
            'mode': mode,
            'image': image_base64,
            'metadata': {
                'size': f"{image.width}x{image.height}",
                'mode': image.mode
            }
        }
        
        # 转换为JSON
        json_data = json.dumps(data)
        
        # 设置请求头
        headers = {
            'Content-Type': 'application/json',
            'Content-Length': len(json_data)
        }
        
        # 发送POST请求
        # print("Sending image to server...")
        conn.request('POST', '/upload', json_data, headers)
        
        # 获取响应
        response = conn.getresponse()
        response_data = response.read().decode('utf-8')
        
        # 解析响应
        result = json.loads(response_data)
        
        # 打印结果
        print(f"Response status: {response.status}")
        print(f"Server response: {result}")
        
        if response.status == 200:
            print("✅ Image sent successfully!")
            if 'text' in result:
                text = result['text']
                print(f"   Server received image text: {text}")
            return 200, text
        else:
            print("❌ Failed to send image")
            return -1, None
            
        # 关闭连接
        conn.close()
        
    except Exception as e:
        print(f"Error sending image: {e}")
        return -1, None


def get_first_number(s):
    match = re.search(r'\d+', s)
    return match.group() if match else ''

def analyze_message_bsc(message):
    flag = False
    mark = ""
    for condition in condition_feature:
        if condition in message.lower():
            flag = True
            mark = condition
    if not flag:
        return None
    if Config["awacsMetricUnit"] == "km":
        if not any(nm in message.lower() for nm in km_feature):
            return None
    elif Config["awacsMetricUnit"] == "nm":
        if not any(nm in message.lower() for nm in nm_feature):
            return None
    parts = message.lower().split()
    try:
        # 朝向存在于还有"°"的部分中
        bearing_part = next((part for part in parts if "°" in part or "*" in part), None)
        if bearing_part is None:
            return None
        bearing = int(re.search(r'\d+', bearing_part).group())
        callsign = parts[0][0]
        condition_index = -1
        for i, part in enumerate(parts):
            if mark in part:
                condition_index = i
                break
        if condition_index == -1:
            return None
        if "hot" in parts[condition_index]:
            heading = (bearing + 180) % 360
            condition = 1
        elif "cold" in parts[condition_index]:
            heading = bearing
            condition = -1
        elif "flank" in parts[condition_index]:
            heading = (bearing + 90) % 360
            condition = 0
        elif "beam" in parts[condition_index]:
            heading = (bearing + 270) % 360
            condition = 0
        
        if Config["awacsMetricUnit"] == "km":
            distance_part = next((part for part in parts if "km" in part), None)
            if distance_part is None:
                return None
            distance = float(re.search(r'[\d.]+', distance_part).group())
            height_part = next((part for part in parts if "m" in part), None)
            if height_part is None:
                return None
            height = float(re.search(r'[\d.]+', height_part).group())
        elif Config["awacsMetricUnit"] == "nm":
            distance_part = next((part for part in parts if "nm" in part), None)
            if distance_part is None:
                return None
            distance = float(re.search(r'[\d.]+', distance_part).group())
            height_part = next((part for part in parts if "ft" in part), None)
            if height_part is None:
                return None
            height = float(re.search(r'[\d.]+', height_part).group())
            
        return {
            "callsign": callsign,
            "bearing": bearing,
            "distance": distance,
            "height": height,
            "heading": heading,
            "condition": condition
        }
        
    except Exception as e:
        print(f"Error analyzing message: {e}")
        return None
        

def analyze_message_sps(message):
    # 如果消息中含有condition_feature中的任意一个词，则继续，否则返回None
    flag = False
    mark = ""
    for condition in condition_feature:
        if condition in message.lower():
            flag = True
            mark = condition
    if not flag:
        return None
    if Config["awacsMetricUnit"] == "km":
        if not any(nm in message.lower() for nm in km_feature):
            return None
    elif Config["awacsMetricUnit"] == "nm":
        if not any(nm in message.lower() for nm in nm_feature):
            return None
    parts = message.lower().split()
    # 寻找hot、cold、flank关键词的位置，作为基础索引
    if len(parts) < 10:
        return None
    
    condition_index = -1
    for i, part in enumerate(parts):
        if mark in part:
            condition_index = i
            break
    try:
        # 获取敌机朝向
        heading = int(parts[condition_index - 1])
        # 检查速度单位
        if not ("knts" in parts[condition_index - 2].lower() or "km" in parts[condition_index - 2].lower()):
            # 获取敌机距离
            return None
        # 获取敌机速度
        speed = float(parts[condition_index - 3])
        # 速度转化为马赫速
        if "knts" in parts[condition_index - 2].lower():
            speed = speed * 1.852 * 0.0008098477486
        elif "km" in parts[condition_index - 2].lower():
            speed = speed * 0.0008098477486 
        # 检查高度单位
        if not ("ft" in parts[condition_index - 4].lower() or "m" in parts[condition_index - 4].lower()):
            return None
        # 获取敌机高度, 写法是1，000,因此只取shuzi
        height_str = parts[condition_index - 5].replace(",", "")
        height = float(height_str)
        
        # 检查距离单位
        if not ("nm" in parts[condition_index - 6].lower() or "km" in parts[condition_index - 6].lower()):
            return None
        # 获取敌机距离
        distance_str = parts[condition_index - 7].replace(",", ".")
        distance = float(distance_str)
        
        # 获取敌机相对本机位置
        bearing = int(parts[condition_index - 8])
        
        # 获取敌机名称，仅获取parts[0]第一次出现的连续数字
        callsign = get_first_number(parts[0])
        if callsign == "":
            return None
        
        return {
            "callsign": callsign,
            "bearing": bearing,
            "distance": distance,
            "height": height,
            "speed": speed,
            "heading": heading,
        }
    except Exception as e:
        print(f"解析消息时发生错误: {e}")
        return None

def awacs_mode(screenShotList, key_callsign, message_dic, bullseye_dic,
                          plane_x, plane_z, metric_unit, bullseye_x, bullseye_z
                            ):
    start_time = time()
    for img in screenShotList:
        code, text = send_image_to_server(0, img, serverInforDetail["serverIP"], serverInforDetail["serverPort"])  
        if code != 200:
            print("Failed to get OCR result from server.")
            continue
        
        for t in text:
            parts = t.replace("，", ",").replace("：",":").replace(".", ",").\
                replace("。", ",").replace("、", ",").replace(";",",").split(",")
            # 去除parts中的空字符串
            parts = [part.strip() for part in parts if part.strip()]
            # print("============================")
            # print("识别的文字：", t)
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
                if "头" in parts[-1]:
                    condition = 1
                elif "追" in parts[-1]:
                    condition = -1
                elif "侧" in parts[-1]:
                    condition = 0
                else:
                    condition = -2  # 未识别到明确的方位关系，设为-2
                
                enemy_altitude = int(''.join(re.findall(r'\d+', "0" + number_mistake_correction(parts[-2]))))
                enemy_distance = int(''.join(re.findall(r'\d+', "0" + number_mistake_correction(parts[-3]))))
                # print("=============================")
                # print("距离: ", enemy_distance,)
                if metric_unit == "nm":
                    enemy_distance = int(enemy_distance * 1852)
                else:
                    enemy_distance = int(enemy_distance * 1000)
                
                enemy_bearing = int(''.join(re.findall(r'\d+', "0" + number_mistake_correction(parts[-4]))))
                if enemy_bearing < 0 or enemy_bearing >= 360:
                    continue
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
                                                    "condition": condition,
                                                    "times": 1,
                                                        }
                else:
                    message_dic[formatted_message]["times"] += 1
                print(message_dic[formatted_message]["times"])
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
                if bulls_enemy_bearing < 0 or bulls_enemy_bearing >= 360:
                    continue
                formatted_message = int(bulls_enemy_altitude + bulls_enemy_distance + bulls_enemy_bearing)
                
                get_time = int(time())
                
                if formatted_message not in bullseye_dic:
                    new_x, new_y = offset_coordinate(bullseye_x, bullseye_z, 
                                                    bulls_enemy_distance, bulls_enemy_bearing)
                    bullseye_dic[formatted_message] = {"timeStamp": get_time,
                                                        "bulls_enemy_altitude": bulls_enemy_altitude,
                                                        "x": new_x,
                                                        "z": new_y,
                                                        "enenmy_heading": -1,
                                                        "times": 0,
                                                        "condition": 0,
                                                        }
                    print("新牛眼消息：", formatted_message) 
                else:
                    bullseye_dic[formatted_message]["times"] += 1
    end_time = time()
    print(f"OCR处理耗时: {end_time - start_time:.2f}秒")
    return message_dic, bullseye_dic

def bsc_mode(screenShotList, message_dic, plane_x, plane_z, metric_unit):
    start_time = time()
    for img in screenShotList:
        code, text = send_image_to_server(1, img, serverInforDetail["serverIP"], serverInforDetail["serverPort"])  
        if code != 200:
            print("Failed to get OCR result from server.")
            continue
        
        for t in text:
            enemy_data = analyze_message_bsc(t)
            if enemy_data == None:
                continue
            if metric_unit == "nm":
                enemy_data["distance"] = int(enemy_data["distance"] * 1852)
            else:
                enemy_data["distance"] = int(enemy_data["distance"] * 1000)
            formatted_message = int(enemy_data["bearing"] + enemy_data["distance"] + enemy_data["height"] + \
                enemy_data["heading"] + enemy_data["condition"])
            get_time = int(time())
            if formatted_message not in message_dic:
                new_x, new_y = offset_coordinate(plane_x, plane_z, enemy_data["distance"], enemy_data["bearing"])
                message_dic[formatted_message] = {"timeStamp": get_time, 
                                                "callsign": enemy_data["callsign"],
                                                "enemy_altitude": enemy_data["height"], 
                                                "enemy_heading": enemy_data["heading"],
                                                "x": new_x,
                                                "z": new_y,
                                                "condition": enemy_data["condition"],
                                                "times": 1,
                                                }
            else:
                message_dic[formatted_message]["times"] += 1
    end_time = time()
    print(f"OCR处理耗时: {end_time - start_time:.2f}秒")
    return message_dic

def sps_mode(screenShotList, message_dic, 
                            plane_x, plane_z, metric_unit):
    start_time = time()
    for img in screenShotList:
        code, text = send_image_to_server(1, img, serverInforDetail["serverIP"], serverInforDetail["serverPort"])  
        if code != 200:
            print("Failed to get OCR result from server.")
            continue
        
        for t in text:
            if t == [] or t == "":
                continue
            enemy_data = analyze_message_sps(t)
            if enemy_data == None:
                continue
            if metric_unit == "nm":
                enemy_data["distance"] = int(enemy_data["distance"] * 1852)
            else:
                enemy_data["distance"] = int(enemy_data["distance"] * 1000)
            formatted_message = int(enemy_data["bearing"] + enemy_data["distance"] + \
                enemy_data["height"] + enemy_data["speed"] + enemy_data["heading"])
            get_time = int(time())
            if formatted_message not in message_dic:
                new_x, new_y = offset_coordinate(plane_x, plane_z, enemy_data["distance"], enemy_data["bearing"])
                message_dic[formatted_message] = {"timeStamp": get_time, 
                                                    "enemy_altitude": enemy_data["height"], 
                                                    "enemy_heading": enemy_data["heading"],
                                                    "x": new_x,
                                                    "z": new_y,
                                                    "condition": -2,
                                                    "times": 2,
                                                    "speed": enemy_data["speed"],
                                                    "callsign": enemy_data["callsign"]
                                                        }
            else:
                message_dic[formatted_message]["times"] += 1
        
        
    end_time = time()
    print(f"OCR处理耗时: {end_time - start_time:.2f}秒")
    return message_dic
            
            
            
            

def get_enemy_bearing_OCR_flask(screenShotList, key_callsign, message_dic, bullseye_dic,
                          plane_x, plane_z, metric_unit, bullseye_x, bullseye_z
                          ):
    to_delete = []
    for key in message_dic:
        if int(time() - message_dic[key]["timeStamp"]) > Config["remainingTime"]:
            to_delete.append(key)
    for key in to_delete:        del message_dic[key]
    # print("当前敌机列表和具体信息：\n", [(k, v) for k, v in message_dic.items()])
    to_delete.clear()
    
    for key in bullseye_dic:
        if int(time() - bullseye_dic[key]["timeStamp"]) > Config["remainingTime"]:
            to_delete.append(key)
    for key in to_delete:        del bullseye_dic[key]
    # print("当前牛眼列表和具体信息：\n", [(k, v) for k, v in bullseye_dic.items()])
    to_delete.clear()
    
    if Config["mode"] == 0:
        message_dic, bullseye_dic = awacs_mode(screenShotList, key_callsign, message_dic, bullseye_dic,
                          plane_x, plane_z, metric_unit, bullseye_x, bullseye_z
                          )
        
    elif Config["mode"] == 1:
        message_dic = sps_mode(screenShotList, message_dic, 
                            plane_x, plane_z, metric_unit)
    elif Config["mode"] == 2:
        message_dic = bsc_mode(screenShotList, message_dic, 
                            plane_x, plane_z, metric_unit)
    
    return message_dic, bullseye_dic
    
    
if __name__ == '__main__':
    # print("正在准备系统，5秒后开始截图并识别文字...")
    # sleep(5)  # 等待2秒，确保系统准备就绪
    # # # 每300毫秒截图三次
    # screenshotList = []
    # img = take_screenshot(0, 0, 600, 400)
    # screenshotList.append(img)

    # # for i in range(8):
    # #     img_fp = './testpic/'
    # #     det =  img_fp + f'{i+2}.png'
    # #     print(get_text_from_image(det))
    # a, b = get_enemy_bearing_OCR_flask(
    #     screenshotList, {"text": "", "num": "11"}, {}, {},
    #                       0, 0, "km", -61910 , +18406, 122
    # # )
    # img = Image.open('./testpic/5.png')
    # enhancer = ImageEnhance.Brightness(img)
    # img = enhancer.enhance(0.5)  # 降低亮度
    # enhancer = ImageEnhance.Contrast(img)
    # img = enhancer.enhance(2)  # 提高对比度
    # img.show()
    det = "./testpic/ewrv6.png"
    textlist = send_image_to_server(1, Image.open(det), "121.41.75.139", 10386)[1]
    for text in textlist:
        result = analyze_message_bsc(text)
        if result != None:
            print(result)
    
    for i in range(4):
        img_fp = './testpic/ewr'
        det =  img_fp + f'{i+1}.png'
        textlist = send_image_to_server(1, Image.open(det), "121.41.75.139", 10386)[1]
        for text in textlist: 
            # text = text.replace("，", ",").replace("：",":").replace(".", ",").\
            #     replace("。", ",").replace("、", ",").replace(";",",")
            result = analyze_message_sps(text)
            if result != None:
                print(result)