from PySide6.QtCore import QObject, Signal

from wordsOCRFlask import get_enemy_bearing_OCR_flask

class operateAwacsMarkRemoteWorker(QObject):
    data_received = Signal(object)  # 定义一个信号，用于传递接收到的数据
    def __init__(self, parent=None, screenShortList_copy=None, callSign=None, message_dic=None, 
                                   bullseye_dic=None, plane_data=None, metric_unit=None, bullseye=None):
        super().__init__(parent)
        self.running = False
        self.screenShortList_copy = screenShortList_copy
        self.callSign = callSign
        self.message_dic = message_dic
        self.bullseye_dic = bullseye_dic
        self.plane_data = plane_data
        self.metric_unit = metric_unit
        self.bullseye = bullseye

    def start_working(self):
        self.running = True
        try:
            message_dicAndbullseye_dic = get_enemy_bearing_OCR_flask(
                self.screenShortList_copy, self.callSign, 
            self.message_dic, self.bullseye_dic, self.plane_data['x'], 
            self.plane_data['z'], self.metric_unit, self.bullseye["x"],
            self.bullseye["z"]
            )
            self.data_received.emit(message_dicAndbullseye_dic)
        except Exception as e:
            print(f"监听过程中发生错误: {e}")
            self.data_received.emit(self.message_dic, self.bullseye_dic)  # 发生错误时发送 None 或其他适当的值
        finally:
            self.running = False
            self.screenShortList_copy = None
            self.callSign = None
            self.message_dic = None
            self.bullseye_dic = None
            self.plane_data = None
            self.metric_unit = None
            self.bullseye = None
            
    def stop_working(self):
        self.running = False
        self.screenShortList_copy = None
        self.callSign = None
        self.message_dic = None
        self.bullseye_dic = None
        self.plane_data = None
        self.metric_unit = None
        self.bullseye = None