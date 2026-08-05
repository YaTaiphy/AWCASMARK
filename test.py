# MiG-29 Fulcrum 191 141,1 NM 8,000 ft 649 Knts 348 Hot
# MiG-295 193 142.9 NM 6,000 ft 544 Knts 013 Hot
# IL-76MD 211 195.3 NM 20,000 ft 399 Knts 023 Hot
# IL-76MD 209 258.8 NM 20,000 ft 399 Knts 023 Hot
# F-16C_50  194 125.2 NM 5,000 ft 643 Knts 252 Flank Right
# Mig-29 Fulcrum 194 137.2 NM
# ~YSUNC3FRS: 6530015778,469 192 Cold
# Mig-29 Fulcrum 174 99.6 NM 2,000 ft 604 Knts 351 Hot
# Mig-29 Fulcrum 194 122.2 NM 7,000 ft 661 Knts 025 Hot
# F-16C 50 193 124.1 NM 5,000 ft 621 Knts 009 Hot
# F-16C_50 192 142.8 NM 14,000 ft 657 Knts 004 Hot
# IL-76MD 209 238.9 NM 20,000 ft 399 Knts 023 Hot
# FA-18C hornet 287 159.7 Km 7,000 m 935 Km/h 090 Hot
from AWACASMARK_config import Config
import re
nm_feature = ["nm", "feet"]
km_feature = ["km", "m"]

condition_feature = ["hot", "cold", "flank"]

def get_first_number(s):
    match = re.search(r'\d+', s)
    return match.group() if match else ''

def analyze_message(message_parts):
    # 如果消息中含有condition_feature中的任意一个词，则继续，否则返回None
    # if not any(condition in message.lower() for condition in condition_feature):
    #     return None
    # if Config["awacsMetricUnit"] == "km":
    #     if not any(nm in message.lower() for nm in km_feature):
    #         return None
    # elif Config["awacsMetricUnit"] == "nm":
    #     if not any(nm in message.lower() for nm in nm_feature):
    #         return None
    # parts = message.lower().split()
    # 寻找hot、cold、flank关键词的位置，作为基础索引
    
    # 对每个parts进行lower处理
    parts = message_parts
    
    if len(parts) < 10:
        return None
    
    condition_index = -1
    for i, part in enumerate(parts):
        if part in condition_feature:
            condition_index = i
            break
    try:
        # 获取敌机朝向
        heading = int(parts[condition_index - 1])
        # 检查速度单位
        if not "knts" or "km" in parts[condition_index - 2].lower():
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
        if not "ft" or "m" in parts[condition_index - 4].lower():
            return None
        # 获取敌机高度, 写法是1，000,因此只取shuzi
        height_str = parts[condition_index - 5].replace(",", "")
        height = float(height_str)
        
        # 检查距离单位
        if not "nm" or "km" in parts[condition_index - 6]:
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
    

        
    
if __name__ == "__main__":
    test_message = "MiG-29 Fulcrum 191 141,1 NM 8,000 ft 649 Knts 348 Hot\n\
                    MiG-295 193 142.9 NM 6,000 ft 544 Knts 013 Hot\n\
                    IL-76MD 211 195.3 NM 20,000 ft 399 Knts 023 Hot\n\
                    IL-76MD 209 258.8 NM 20,000 ft 399 Knts 023 Hot\n\
                    F-16C_50  194 125.2 NM 5,000 ft 643 Knts 252 Flank Right\n\
                    Mig-29 Fulcrum 194 137.2 NM\n\
                    ~YSUNC3FRS: 6530015778,469 192 Cold\n\
                    Mig-29 Fulcrum 174 99.6 NM 2,000 ft 604 Knts 351 Hot\n\
                    Mig-29 Fulcrum 194 122.2 NM 7,000 ft 661 Knts 025 Hot\n\
                    F-16C 50 193 124.1 NM 5,000 ft 621 Knts 009 Hot\n\
                    F-16C_50 192 142.8 NM 14,000 ft 657 Knts 004 Hot\n\
                    IL-76MD 209 238.9 NM 20,000 ft 399 Knts 023 Hot\n\
                    FA-18C hornet 287 159.7 Km 7,000 m 935 Km/h 090 Hot"
    sentences = test_message.split("\n")
    for sentence in sentences:
        print(f"解析消息: {sentence}")
        result = analyze_message(sentence)
        print(result)