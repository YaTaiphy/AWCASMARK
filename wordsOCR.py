from cnocr import CnOcr
from time import sleep, time
from mss import mss
from PIL import Image
import numpy as np
from time import sleep
import re, os
# import easyocr
from utils import alphabet_mistacke_correction, number_mistake_correction, offset_coordinate
from wordsOCRFlask import analyze_message

model_root = os.path.join(os.getcwd(), 'models')
if not os.path.exists(model_root):
    os.makedirs(model_root)
# ocr = CnOcr(model_name="doc-densenet_lite_136-gru")
# ocr = CnOcr(rec_model_name='doc-densenet_lite_136-gru')  # 所有参数都使用默认值
ocr = CnOcr(det_root=model_root, rec_root=model_root,  \
            rec_model_name='doc-densenet_lite_136-gru', \
            # det_model_name='en_PP-OCRv3_det',\
            context='cpu'
            )  # 所有参数都使用默认值
# ocr = CnOcr(det_model_name='ch_PP-OCRv5_det',rec_model_name='ch_PP-OCRv4')  # 所有参数都使用默认值

# reader = easyocr.Reader(['en'], gpu=False, model_storage_directory=model_root, user_network_directory=model_root)

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
        return img



def get_text_from_image(image_path):
    out = ocr.ocr(image_path)
    text = [item['text'] for item in out]
    return text

def group_text_by_lines(ocr_results, y_threshold=10):
    if not ocr_results:
        return [[]]
    
    lines = ""
    texts = []
    current_y = None
    
    for item in ocr_results:
        text = item['text']
        y = item['position'][3][1]  # 获取文本框的y坐标
        
        if current_y is None:
            current_y = item['position'][2][1]  # 初始化当前行的y坐标
        
        # 如果当前文本的y坐标与当前行的y坐标差距较大，认为是新的一行
        if abs(y - current_y) > y_threshold:
            texts.append(lines)
            lines = ""  # 开始新的一行
            lines += text + " "  # 将文本添加到新行
        else:
            lines += text + " "  # 将文本添加到当前行
        current_y = item['position'][2][1]
    texts.append(lines)  # 添加最后一行
    
    return texts

def get_text_from_image_sps(image_path):
    # results = reader.readtext(
    #     image_path,
    #     paragraph=True,          # 段落模式保留结构
    #     x_ths=10,              # 字符间距阈值
    #     y_ths=0.1,              # 行间距阈值
    #     text_threshold=0.7,      # 标准阈值
    #     low_text=0.3,            # 低文字检测
    #     mag_ratio=1.5,           # 小字体放大
    #     detail=0,                # 只返回文本
    # )
    out = ocr.ocr(image_path)
    # 如果高度差不大，认为是同一行文本，存储在同一个列表中
    text_lines = group_text_by_lines(out)
    
    return text_lines

def get_enemy_bearing_OCR(screenShotList, key_callsign, message_dic, bullseye_dic,
                          plane_x, plane_z, metric_unit, bullseye_x, bullseye_z, plane_heading
                          ):
    start_time = time()
    to_delete = []
    for key in message_dic:
        if int(time() - message_dic[key]["timeStamp"]) > 90:
            to_delete.append(key)
    for key in to_delete:        del message_dic[key]
    # print("当前敌机列表和具体信息：\n", [(k, v) for k, v in message_dic.items()])
    to_delete.clear()
    
    for key in bullseye_dic:
        if int(time() - bullseye_dic[key]["timeStamp"]) > 90:
            to_delete.append(key)
    for key in to_delete:        del bullseye_dic[key]
    # print("当前牛眼列表和具体信息：\n", [(k, v) for k, v in bullseye_dic.items()])
    to_delete.clear()
    
    
    for img in screenShotList:
        text = get_text_from_image(np.array(img))   
        
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
    end_time = time()
    print(f"OCR处理耗时: {end_time - start_time:.2f}秒")
    return message_dic, bullseye_dic
    
    
if __name__ == '__main__':
    # print("正在准备系统，5秒后开始截图并识别文字...")
    # sleep(5)  # 等待2秒，确保系统准备就绪
    # # # 每300毫秒截图三次
    # screenshotList = []
    # img = take_screenshot(0, 0, 600, 400)
    # screenshotList.append(img)
    sentences = []
    for i in range(4):
        img_fp = './testpic/ewr'
        det =  img_fp + f'{i+1}.png'
        textlist = get_text_from_image_sps(det)
        print(textlist)
        for text in textlist: 
            # text = text.replace("，", ",").replace("：",":").replace(".", ",").\
            #     replace("。", ",").replace("、", ",").replace(";",",")
            print(text)
            sentences.append(text)
    
    for sentence in sentences:
        # print(f"解析消息: {sentence}")
        result = analyze_message(sentence)
        if result != None:
            print(result)
    
    