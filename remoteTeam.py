import time
import json
from PySide6.QtCore import QObject, Signal
from serverInfor import serverInforDetail
from AWACASMARK_config import Config
import http.client

# self.plane_data = {            "heading": 270,
#     "x": 0,
#     "y": 0,
#     "z": 0,
#     "height": 0}  # 用于存储飞机数据的字典
def get_team_mate_info_flask(plane_data):
    """发送请求到Flask服务器获取队友信息"""
    try:
        # 准备连接
        conn = http.client.HTTPConnection(serverInforDetail["serverIP"], serverInforDetail["serverPort"], timeout=10)
        callSign = ""
        if Config["callSign"]["text"] != "":
            callSign = Config["callSign"]["text"][0] + str(Config["callSign"]["num"])
        else:
            callSign = Config["callSign"]["num"]
        data = {
            "teamcode": Config["teamcode"],
            "heading": plane_data['heading'],
            "x": plane_data['x'],
            "y": plane_data['y'],
            "z": plane_data['z'],
            "timestamp": int(time.time()),
            "callSign": callSign,
            "id": Config["id"]
        }
        
        json_data = json.dumps(data)
        headers = {'Content-type': 'application/json',
                   'Content-length': len(json_data)}
        # 发送POST请求
        conn.request('POST', '/team', json_data, headers)
        
        # 获取响应
        response = conn.getresponse()
        if response.status == 200:
            team_data = response.read().decode('utf-8')
            results = json.loads(team_data)
            print(f"从服务器获取的队友数据: {results}")
            # 返回值为一组队友信息，为队列，每个格式如下：{
            #     "teamcode": Config["teamcode"],
            #     "heading": plane_data['heading'],
            #     "x": plane_data['x'],
            #     "y": plane_data['y'],
            #     "z": plane_data['z'],
            #     "timestamp": int(time.time()),
            #     "callSign": callSign
            # }
            # 去除自己的信息
            results = [mate for mate in results if mate['id'] != Config["id"]]
            print(f"去除自身信息后的队友数据: {results}")
            return 200, results  # 返回队友信息
        else:
            print(f"请求失败，状态码: {response.status}")
            return -1, None  # 请求失败
    except Exception as e:
        print(f"from serverInfor import serverInfor: {e}")
        return -1, None  # 发生错误
    finally:
        conn.close()

class operateTeamMateMarkRemoteWorker(QObject):
    data_received = Signal(object)  # 定义一个信号，用于传递接收到的数据
    def __init__(self, parent=None, plane_data=None):
        super().__init__(parent)
        self.running = False
        self.plane_data = plane_data

    def start_working(self):
        self.running = True
        try:
            # 在这里添加获取队友信息的逻辑，并将结果通过信号发送出去
            status, team_data = get_team_mate_info_flask(self.plane_data)
            if status == 200:
                self.data_received.emit(team_data)
            else:
                self.data_received.emit(None)
        except Exception as e:
            print(f"监听过程中发生错误: {e}")
            self.data_received.emit(None)  # 发生错误时发送 None 或其他适当的值
            
    def stop_working(self):
        self.running = False