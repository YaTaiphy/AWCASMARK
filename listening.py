import socket
from PySide6.QtCore import QObject, QThread, Signal

class SocketWorker(QObject):
    data_received = Signal(str)  # 定义一个信号，用于传递接收到的数据

    def __init__(self, parent=None):
        super().__init__(parent)
        self.running = False
        self.sock = None
        
    def socket_receive(self):
        # 创建 UDP Socket
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        server_address = ('127.0.0.1', 12345)
        self.sock.bind(server_address)
        try:
            while self.running:
            # 使用非阻塞方式接收
                try:        
                    # 绑定到本地地址和端口（与 Lua 中配置的端口一致）
                    data, address = self.sock.recvfrom(1024)
                    message = data.decode('utf-8').strip()
                    self.data_received.emit(message)
                    # parts = message.split(',')
                    # if len(parts) == 10:
                    #     timestamp = float(parts[0])
                    #     pos_x = float(parts[1])
                    #     pos_y = float(parts[2])
                    #     pos_z = float(parts[3])
                    #     heading = float(parts[4])
                    #     pitch = float(parts[5])
                    #     bank = float(parts[6])
                    #     lat = float(parts[7])
                    #     long = float(parts[8])
                    #     height = float(parts[9])
                        
                    #     # 打印数据，可根据需要替换为其他处理逻辑
                    #     print(f"航向: {heading:.4f}  | ----")
                    # else:
                        # print(f"收到格式错误的数据: {message}")
                except BlockingIOError:
                    # 非阻塞模式下的正常情况
                    pass
                # # 使用更精确的定时器替代sleep
                # QThread.msleep(1000/30)  # PyQt内置的毫秒级睡眠
        except Exception as e:
            print(f"监听内循环过程中发生错误: {e}")
        finally:
            if self.sock:
                self.sock.close()
                
    def start_listening(self):
        self.running = True
        try:
            while self.running:
                self.socket_receive()
        except Exception as e:
            print(f"监听外循环过程中发生错误: {e}")
        finally:
            if self.sock:
                self.sock.close()
            self.running = False
            
    
    def stop_listening(self):
        self.running = False
        if self.sock:
            self.sock.close()

def main():
    # 创建 UDP Socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    # 绑定到本地地址和端口（与 Lua 中配置的端口一致）
    server_address = ('127.0.0.1', 12345)
    sock.bind(server_address)
    
    print("正在监听 DCS 数据，按 Ctrl+C 停止...")
    
    try:
        while True:
            # 接收数据，缓冲区大小为 1024 字节
            data, address = sock.recvfrom(1024)
            # 解码为字符串
            message = data.decode('utf-8').strip()
            
            print(f"收到数据: {message} 来自 {address}")
            
            # 解析字符串，格式: TIME,PosX,PosY,PosZ,Heading,Pitch,Bank
            parts = message.split(',')
            if len(parts) == 10:
                timestamp = float(parts[0])
                pos_x = float(parts[1])
                pos_y = float(parts[2])
                pos_z = float(parts[3])
                heading = float(parts[4])
                pitch = float(parts[5])
                bank = float(parts[6])
                lat = float(parts[7])
                long = float(parts[8])
                height = float(parts[9])
                
                # 打印数据，可根据需要替换为其他处理逻辑
                print(f"时间: {timestamp:.3f} | 位置: ({pos_x:.2f}, {pos_y:.2f}, {pos_z:.2f}) | "
                      f"航向: {heading:.4f}  | 俯仰: {pitch:.4f}  | 横滚: {bank:.4f} | 纬度: {lat:.4f} | 经度: {long:.4f} | 高度: {height:.4f}")
            else:
                print(f"收到格式错误的数据: {message}")
                
    except KeyboardInterrupt:
        print("\n程序已停止")
    finally:
        sock.close()

if __name__ == "__main__":
    main()