import sys
import os
import json
import urllib.request
import subprocess

# ===================== Qt平台插件路径设置（PyInstaller打包必需） =====================
if getattr(sys, 'frozen', False):
    # 打包后的情况：设置Qt插件路径
    qt_plugin_path = os.path.join(sys._MEIPASS, 'PyQt5', 'Qt5', 'plugins')
    if not os.path.exists(qt_plugin_path):
        qt_plugin_path = os.path.join(sys._MEIPASS, 'PyQt5', 'Qt', 'plugins')
    os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = qt_plugin_path

import time
import struct
import serial
import serial.tools.list_ports
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
import pyqtgraph as pg
import threading

# ===================== 配置管理 =====================
def load_config():
    """加载配置文件，如果不存在或格式错误则返回默认配置"""
    default_config = {
        "version_check_url": "",
        "check_on_startup": True,
        "current_version": "1.2.0"
    }
    
    try:
        # 获取正确的配置文件路径
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')
        
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                print(f"✅ 成功加载配置文件: {config_path}")
                return config
        else:
            print(f"⚠️ 配置文件不存在: {config_path}，使用默认配置")
            # 创建默认配置文件
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=2, ensure_ascii=False)
            return default_config
    except Exception as e:
        print(f"❌ 加载配置文件失败: {str(e)}，使用默认配置")
        return default_config

# 加载配置
APP_CONFIG = load_config()

# ===================== 版本信息 =====================
CURRENT_VERSION = APP_CONFIG.get("current_version", "1.2.0")

# 远程版本检查URL（从配置文件读取，支持动态更新）
VERSION_CHECK_URL = APP_CONFIG.get("version_check_url", "") 

VERSION_HISTORY = [
    {
        "version": "1.0.0",
        "date": "2026-05-26",
        "title": "初始版本",
        "changes": [
            "✅ 基础功能实现：串口通信、数据采集、实时监控",
            "✅ 支持11路应变片数据采集与显示",
            "✅ 支持8路陀螺仪数据采集与实时曲线显示",
            "✅ 气象环境参数监测（风速、温湿度、PM2.5等）",
            "✅ 电机控制与声光报警功能",
            "✅ 科幻风格UI界面设计"
        ]
    },
    # 后续版本更新请在此添加新版本记录
    {
        "version": "1.1.0",
        "date": "2026-05-26",
        "title": "功能优化",
        "changes": [
            "✨ 新增了版本管理功能",
        ]
    },
    # 后续版本更新请在此添加新版本记录
    {
        "version": "1.2.0",
        "date": "2026-05-26",
        "title": "功能优化",
        "changes": [
            "✨ 测试 用户版本更新功能",
        ]
    }    
]

# ===================== CRC16 校验（修正字节序,与Modbus RTU完全一致） =====================
def crc16_modbus(data):
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            if crc & 1:
                crc >>= 1
                crc ^= 0xA001
            else:
                crc >>= 1
    return crc

def check_crc(buf):
    if len(buf) < 3:
        return False
    data_len = len(buf) - 2
    data = buf[:data_len]
    recv_crc = (buf[data_len + 1] << 8) | buf[data_len]
    calc_crc = crc16_modbus(data)
    return recv_crc == calc_crc

# ===================== 协议固定指令 =====================
CMD_MAIN = bytes([0x01, 0x03, 0x03, 0x01, 0x00, 0x18, 0x14, 0x44])
CMD_GYRO = bytes([0x02, 0x03, 0x03, 0x01, 0x00, 0x60, 0x14, 0x55])

MOTOR_ON  = bytes([0x01,0x06,0x06,0x01,0x00,0x01,0x19,0x42])
MOTOR_OFF = bytes([0x01,0x06,0x06,0x01,0x00,0x00,0xD8,0x82])
ALARM_ON  = bytes([0x03,0x06,0x00,0x63,0x00,0xFF,0x38,0x76])
ALARM_OFF = bytes([0x03,0x06,0x00,0x63,0x00,0x00,0x78,0x36])

# ===================== 全局样式 =====================
GLOBAL_STYLE = """
QWidget{background-color: #071f3a;}
QScrollArea{background-color: transparent;}
QFrame{background-color: transparent;}
QMainWindow{background-color: #071f3a;}

/* 科幻风格GroupBox - 增强边框和发光效果 */
QGroupBox{
    color: #E6F2FF;
    font-size:14px;
    font-weight:bold;
    background-color:#081827;
    border: 2px solid #0ea5e9;
    border-radius:12px;
    margin-top:16px;
    padding-top:18px;
    box-shadow: 0 0 15px rgba(14, 165, 233, 0.3);
}
QGroupBox::title{
    subcontrol-origin: margin;
    left:20px;
    top:8px;
    color: #60a5fa;
    text-shadow: 0 0 10px rgba(96, 165, 250, 0.7);
}

/* 科幻风格标签 */
QLabel{
    color:#C9E6FF;
    font-size:13px;
    text-shadow: 0 0 5px rgba(201, 230, 255, 0.5);
}

/* 科幻游戏风格按钮 - 增强发光和动画效果 */
QPushButton{
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #0EA5E9, stop:1 #0284C7);
    color:#FFFFFF;
    border: 2px solid #3b82f6;
    border-radius:8px;
    padding:10px 24px;
    font-size:14px;
    font-weight:bold;
    box-shadow: 0 0 12px rgba(14, 165, 233, 0.4);
    text-shadow: 0 0 8px rgba(255, 255, 255, 0.6);
}
QPushButton:hover{
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #3b82f6, stop:1 #0b79b0);
    border: 2px solid #60a5fa;
    box-shadow: 0 0 20px rgba(96, 165, 250, 0.6);
}
QPushButton:disabled{
    background-color:#143444;
    color:#6b7f8e;
    border: 2px solid #2d4a5d;
    box-shadow: none;
}

/* 科幻风格下拉框 */
QComboBox{
    background-color:#042b40;
    color:#E6F2FF;
    border: 2px solid #184e85;
    border-radius:8px;
    padding:8px 12px;
    font-size:13px;
    box-shadow: 0 0 8px rgba(24, 78, 133, 0.3);
}
QComboBox QAbstractItemView{
    background-color:#042b40;
    color:#E6F2FF;
    selection-background-color:#0EA5E9;
    border: 2px solid #184e85;
    border-radius:8px;
}

/* 科幻风格文本编辑器 - 终端效果 */
QTextEdit{
    background-color:#022233;
    color:#BEEAF7;
    font-family: 'Courier New', Consolas, monospace;
    font-size:12px;
    border: 2px solid #184e85;
    border-radius:8px;
    box-shadow: inset 0 0 10px rgba(24, 78, 133, 0.4);
}

/* 弹窗样式已在show_alert中定义，保持原样 */
"""

DATA_LABEL_STYLE = """
QLabel{
    background-color:#02293c;
    color:#7FE8FF;
    font-size:16px;
    font-weight:bold;
    padding:8px 6px;
    border: 2px solid #184e85;
    border-radius:8px;
    min-width:120px;
    text-align:center;
    box-shadow: 0 0 10px rgba(127, 232, 255, 0.3);
    text-shadow: 0 0 6px rgba(127, 232, 255, 0.7);
}
"""

GYRO_CLICK_STYLE = """
QLabel{
    background-color:#02293c;
    color:#7FE8FF;
    font-size:16px;
    font-weight:bold;
    padding:8px 6px;
    border: 2px solid #184e85;
    border-radius:8px;
    box-shadow: 0 0 8px rgba(127, 232, 255, 0.2);
    text-shadow: 0 0 4px rgba(127, 232, 255, 0.5);
}
QLabel:hover{
    background-color:#0b486b;
    border: 2px solid #60a5fa;
    box-shadow: 0 0 15px rgba(96, 165, 250, 0.5);
    transform: scale(1.05);
}
"""

SELECTED_GYRO_STYLE = """
QLabel{
    background-color:#1e3a8a;
    color:white;
    font-size:16px;
    font-weight:bold;
    padding:8px 6px;
    border: 2px solid #3b82f6;
    border-radius:8px;
    box-shadow: 0 0 20px rgba(59, 130, 246, 0.6);
    text-shadow: 0 0 8px rgba(255, 255, 255, 0.8);
}
"""

# ===================== 工具函数 =====================
def decode_int16(val):
    if val > 32767:
        return val - 65536
    return val

def hex_str(buf):
    return ' '.join(f'{b:02X}' for b in buf)

# ===================== 串口线程 =====================
class SerialWorker(QThread):
    sig_data = pyqtSignal(object, int)
    sig_log  = pyqtSignal(str, bool)
    sig_cmd_result = pyqtSignal(bytes, bool, bytes)

    def __init__(self, port, baud, cmd, dev_id, sample_interval=0.5):
        super().__init__()
        self.port = port
        self.baud = baud
        self.cmd = cmd
        self.dev_id = dev_id
        self.sample_interval = sample_interval
        self.running = True
        self.ser = None
        self.ser_lock = threading.Lock()

    def run(self):
        try:
            self.ser = serial.Serial(self.port, self.baud, timeout=0.5)
            self.sig_log.emit(f"✅ 已连接 {self.port} {self.baud}", False)
        except Exception as e:
            self.sig_log.emit(f"❌ 连接失败：{str(e)}", True)
            return

        while self.running:
            if not self.ser or not self.ser.is_open:
                break
            try:
                with self.ser_lock:
                    self.ser.write(self.cmd)
                    buf = self.ser.read(200)
                if len(buf) > 0:
                    self.sig_log.emit(f"📥 收到帧: {hex_str(buf)}", False)

                if len(buf) < 8:
                    self.sig_log.emit(f"⚠️ 数据过短，丢弃", True)
                    continue

                if not check_crc(buf):
                    self.sig_log.emit(f"❌ CRC 校验失败 → 数据无效", True)
                    continue

                self.sig_log.emit(f"✅ 校验通过 → 解析数据", False)
                if self.dev_id == 0:
                    data = self.parse_main(buf)
                else:
                    data = self.parse_gyro(buf)
                self.sig_data.emit(data, self.dev_id)

            except Exception as e:
                self.sig_log.emit(f"❌ 异常：{str(e)}", True)
            time.sleep(self.sample_interval)

        if self.ser:
            self.ser.close()
        self.sig_log.emit("🔌 串口已断开", False)

    def parse_main(self, buf):
        d = {}
        off = 3
        d["tunnel1"] = decode_int16((buf[off]<<8)|buf[off+1]); off +=2
        d["tunnel2"] = decode_int16((buf[off]<<8)|buf[off+1]); off +=2
        d["tunnel3"] = decode_int16((buf[off]<<8)|buf[off+1]); off +=2
        d["bridge1"] = decode_int16((buf[off]<<8)|buf[off+1]); off +=2
        d["bridge2"] = decode_int16((buf[off]<<8)|buf[off+1]); off +=2
        d["bridge3"] = decode_int16((buf[off]<<8)|buf[off+1]); off +=2
        d["bridge4"] = decode_int16((buf[off]<<8)|buf[off+1]); off +=2
        d["bridge5"] = decode_int16((buf[off]<<8)|buf[off+1]); off +=2
        d["free1"]   = decode_int16((buf[off]<<8)|buf[off+1]); off +=2
        d["free2"]   = decode_int16((buf[off]<<8)|buf[off+1]); off +=2
        d["free3"]   = decode_int16((buf[off]<<8)|buf[off+1]); off +=2
        d["settle"]  = decode_int16((buf[off]<<8)|buf[off+1]); off +=2

        d["wind_speed"] = ((buf[off]<<8)|buf[off+1])/10.0; off +=2
        d["wind_level"]  = (buf[off]<<8)|buf[off+1]; off +=2
        d["wind_gear"]   = (buf[off]<<8)|buf[off+1]; off +=2
        d["wind_angle"]  = (buf[off]<<8)|buf[off+1]; off +=2
        d["humidity"]    = ((buf[off]<<8)|buf[off+1])/10.0; off +=2
        d["temp"]        = decode_int16((buf[off]<<8)|buf[off+1])/10.0; off +=2
        d["noise"]       = ((buf[off]<<8)|buf[off+1])/10.0; off +=2
        d["pm25"]        = (buf[off]<<8)|buf[off+1]; off +=2
        d["pm10"]        = (buf[off]<<8)|buf[off+1]; off +=2
        d["press"]       = ((buf[off]<<8)|buf[off+1])/10.0; off +=2
        d["line_move"]   = (buf[off]<<24)|(buf[off+1]<<16)|(buf[off+2]<<8)|buf[off+3]; off +=4
        return d

    def parse_gyro(self, buf):
        gyro_list = []
        off = 3
        for _ in range(8):
            pitch = struct.unpack(">f", buf[off:off+4])[0]; off+=4
            roll  = struct.unpack(">f", buf[off:off+4])[0]; off+=4
            yaw   = struct.unpack(">f", buf[off:off+4])[0]; off+=4
            ax    = struct.unpack(">f", buf[off:off+4])[0]; off+=4
            ay    = struct.unpack(">f", buf[off:off+4])[0]; off+=4
            az    = struct.unpack(">f", buf[off:off+4])[0]; off+=4
            gyro_list.append({"pitch":pitch,"roll":roll,"yaw":yaw,"ax":ax,"ay":ay,"az":az})
        return gyro_list

    def send_cmd(self, data):
        if self.ser and self.ser.is_open:
            self.ser.write(data)

    def send_with_retry(self, data, attempts=5, delay=0.1):
        result = False
        last_resp = b''
        if not (self.ser and self.ser.is_open):
            self.sig_log.emit("❌ 串口未打开，无法发送命令", True)
            self.sig_cmd_result.emit(data, False, last_resp)
            return False

        for i in range(1, attempts + 1):
            try:
                with self.ser_lock:
                    self.ser.write(data)
                    self.sig_log.emit(f"📤 发送第{i}次: {hex_str(data)}", False)
                    resp = self.ser.read(len(data))
                last_resp = resp
                if resp == data:
                    self.sig_log.emit(f"✅ 收到应答（匹配）: {hex_str(resp)}", False)
                    result = True
                    break
                else:
                    self.sig_log.emit(f"⚠️ 收到应答: {hex_str(resp)} 与 发送帧不匹配", True)
            except Exception as e:
                self.sig_log.emit(f"❌ 发送异常：{str(e)}", True)
            time.sleep(delay)

        if not result:
            self.sig_log.emit(f"❌ 重试{attempts}次均失败: {hex_str(data)}", True)
        self.sig_cmd_result.emit(data, result, last_resp)
        return result

    def send_with_retry_async(self, data, attempts=5, delay=0.1):
        t = threading.Thread(target=self.send_with_retry, args=(data, attempts, delay), daemon=True)
        t.start()

    def stop(self):
        self.running = False

# ===================== 自动更新线程 =====================
class UpdateChecker(QThread):
    """后台检查版本更新的线程"""
    update_available = pyqtSignal(str, str, str)  # 新版本号, 更新说明, 下载链接
    no_update = pyqtSignal()
    check_error = pyqtSignal(str)

    def __init__(self, current_version, check_url):
        super().__init__()
        self.current_version = current_version
        self.check_url = check_url

    def run(self):
        if not self.check_url:
            self.no_update.emit()
            return

        try:
            # 下载远程版本信息
            with urllib.request.urlopen(self.check_url, timeout=5) as response:
                remote_data = json.loads(response.read().decode('utf-8'))
            
            latest_version = remote_data.get('latest_version', '')
            download_url = remote_data.get('download_url', '')
            update_notes = remote_data.get('update_notes', '')

            # 比较版本号
            if self.compare_versions(latest_version, self.current_version) > 0:
                self.update_available.emit(latest_version, update_notes, download_url)
            else:
                self.no_update.emit()

        except Exception as e:
            self.check_error.emit(f"检查更新失败：{str(e)}")

    def compare_versions(self, v1, v2):
        """比较版本号，v1 > v2 返回 1，v1 < v2 返回 -1，相等返回 0"""
        parts1 = [int(x) for x in v1.split('.')]
        parts2 = [int(x) for x in v2.split('.')]
        
        for p1, p2 in zip(parts1, parts2):
            if p1 > p2:
                return 1
            elif p1 < p2:
                return -1
        
        if len(parts1) > len(parts2):
            return 1
        elif len(parts1) < len(parts2):
            return -1
        
        return 0

class DownloadWorker(QThread):
    """后台下载更新的线程"""
    progress = pyqtSignal(int, int)  # 已下载, 总大小
    finished = pyqtSignal(str)  # 文件路径
    error = pyqtSignal(str)

    def __init__(self, url, save_path):
        super().__init__()
        self.url = url
        self.save_path = save_path
        self.downloading = True

    def run(self):
        try:
            def report_progress(block_num, block_size, total_size):
                if not self.downloading:
                    raise Exception("下载已取消")
                downloaded = block_num * block_size
                self.progress.emit(downloaded, total_size)

            urllib.request.urlretrieve(self.url, self.save_path, report_progress)
            self.finished.emit(self.save_path)

        except Exception as e:
            self.error.emit(f"下载失败：{str(e)}")

    def stop(self):
        self.downloading = False

# ===================== 主窗口 =====================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("桥梁模型箱 485综合采集上位机")
        self.resize(1600,1050)
        self.setStyleSheet(GLOBAL_STYLE)

        self.worker_main = None
        self.worker_gyro = None
        self.alarm_timer = QTimer()
        self.alarm_timer.setInterval(10000)
        self.alarm_timer.timeout.connect(self.close_alarm_auto)
        self.alarm_on_flag = False
        self.last_z = [None]*8
        self._active_msgboxes = []

        self.selected_gyro = 0
        self.max_points = 100
        self.gyro_data_buffer = [{"ax":[],"ay":[],"az":[]} for _ in range(8)]

        self.update_checker = None
        self.download_worker = None
        self.pending_update_file = None

        self.init_ui()
        self.refresh_com_port()
        
        # 显示启动信息
        self.show_startup_info()
        
        # 根据配置决定是否在启动时检查更新
        if APP_CONFIG.get("check_on_startup", True):
            # 延迟1秒后检查更新（等界面加载完成）
            QTimer.singleShot(1000, self.check_for_updates)
        else:
            self.log("ℹ️ 启动时自动检查更新已禁用", False)

    def init_ui(self):
        # 全局滚动布局
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setCentralWidget(scroll_area)

        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(20,20,20,20)
        main_layout.setSpacing(12)

        # 第一行：只放关于按钮（左上角）
        about_layout = QHBoxLayout()
        
        # 关于按钮 - 小巧版本
        self.btn_about = QPushButton("关于")
        self.btn_about.clicked.connect(self.show_about)
        self.btn_about.setStyleSheet("""
            QPushButton {
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #8b5cf6, stop:1 #7c3aed);
                color: #ffffff;
                border: 2px solid #a78bfa;
                border-radius: 6px;
                padding: 6px 16px;
                font-size: 12px;
                font-weight: bold;
                box-shadow: 0 0 8px rgba(139, 92, 246, 0.3);
                text-shadow: 0 0 5px rgba(255, 255, 255, 0.4);
            }
            QPushButton:hover {
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #a78bfa, stop:1 #8b5cf6);
                border: 2px solid #c4b5fd;
                box-shadow: 0 0 12px rgba(167, 139, 250, 0.5);
            }
        """)
        self.btn_about.setFixedWidth(60)
        
        about_layout.addWidget(self.btn_about)
        about_layout.addStretch()
        main_layout.addLayout(about_layout)
        
        # 第二行：主板和陀螺仪设置（水平布局）
        top_layout = QHBoxLayout()
        
        g1 = QGroupBox("模型箱主板 地址0x01")
        l1 = QHBoxLayout(g1)
        self.cb_port1 = QComboBox()
        self.cb_baud1 = QComboBox()
        self.cb_baud1.addItems(["9600","115200"])
        self.cb_baud1.setCurrentText("115200")
        self.btn_conn1 = QPushButton("连接主板")
        self.btn_conn1.clicked.connect(self.toggle_conn_main)
        l1.addWidget(QLabel("COM:"))
        l1.addWidget(self.cb_port1)
        l1.addWidget(QLabel("波特率:"))
        l1.addWidget(self.cb_baud1)
        l1.addWidget(self.btn_conn1)
        top_layout.addWidget(g1)

        g2 = QGroupBox("陀螺仪采集板 地址0x02")
        l2 = QHBoxLayout(g2)
        self.cb_port2 = QComboBox()
        self.cb_baud2 = QComboBox()
        self.cb_baud2.addItems(["9600","115200"])
        self.cb_baud2.setCurrentText("115200")
        self.cb_sample_rate = QComboBox()
        self.cb_sample_rate.addItems(["1Hz", "5Hz", "10Hz"])
        self.cb_sample_rate.setCurrentText("1Hz")
        self.cb_sample_rate.currentTextChanged.connect(self.on_sample_rate_changed)
        self.sample_rate_tip = QLabel("(更改后需重新连接)")
        self.sample_rate_tip.setStyleSheet("color: #9ad6ff; font-size: 11px;")
        self.btn_conn2 = QPushButton("连接陀螺仪板")
        self.btn_conn2.clicked.connect(self.toggle_conn_gyro)
        l2.addWidget(QLabel("COM:"))
        l2.addWidget(self.cb_port2)
        l2.addWidget(QLabel("波特率:"))
        l2.addWidget(self.cb_baud2)
        l2.addWidget(QLabel("采样率:"))
        l2.addWidget(self.cb_sample_rate)
        l2.addWidget(self.sample_rate_tip)
        l2.addWidget(self.btn_conn2)
        top_layout.addWidget(g2)
        main_layout.addLayout(top_layout)

        ctrl_layout = QHBoxLayout()
        self.btn_motor_start = QPushButton("启动振动电机")
        self.btn_motor_stop  = QPushButton("关闭振动电机")
        self.btn_motor_start.clicked.connect(self.send_motor_on)
        self.btn_motor_stop.clicked.connect(self.send_motor_off)
        self.btn_motor_stop.setEnabled(False)
        ctrl_layout.addWidget(self.btn_motor_start)
        ctrl_layout.addWidget(self.btn_motor_stop)
        ctrl_layout.addStretch()
        main_layout.addLayout(ctrl_layout)

        strain_box = QGroupBox("11路应变片数据 (单位：με)")
        strain_layout = QGridLayout(strain_box)
        self.strain_labels = {}
        keys = [
            ("隧道1#","tunnel1"),("隧道2#","tunnel2"),("隧道3#","tunnel3"),
            ("桥梁1#","bridge1"),("桥梁2#","bridge2"),("桥梁3#","bridge3"),
            ("桥梁4#","bridge4"),("桥梁5#","bridge5"),
            ("自由1#","free1"),("自由2#","free2"),("自由3#","free3")
        ]
        r,c=0,0
        for name,k in keys:
            strain_layout.addWidget(QLabel(name), r*2, c)
            lab = QLabel("0")
            lab.setStyleSheet(DATA_LABEL_STYLE)
            lab.setAlignment(Qt.AlignCenter)
            strain_layout.addWidget(lab, r*2+1, c)
            self.strain_labels[k] = lab
            c+=1
            if c>=3: c=0; r+=1
        main_layout.addWidget(strain_box)

        weather_box = QGroupBox("气象环境参数")
        wl = QGridLayout(weather_box)
        self.weather_labels = {}
        items = [
            ("风速(m/s)","wind_speed"),
            ("风力(级)","wind_level"),
            ("风向档","wind_gear"),
            ("风向角度(°)","wind_angle"),
            ("湿度(%RH)","humidity"),
            ("温度(℃)","temp"),
            ("噪声(db)","noise"),
            ("PM2.5","pm25"),
            ("PM10","pm10"),
            ("大气压(kPa)","press"),
            ("沉降(mm)","settle"),
            ("拉线位移","line_move")
        ]
        idx=0
        for name,key in items:
            row = idx // 3
            col = idx % 3
            wl.addWidget(QLabel(name), row*2, col)
            lab = QLabel("0.00")
            lab.setStyleSheet(DATA_LABEL_STYLE)
            lab.setAlignment(Qt.AlignCenter)
            wl.addWidget(lab, row*2+1, col)
            self.weather_labels[key] = lab
            idx +=1
        main_layout.addWidget(weather_box)

        gyro_box = QGroupBox("8路陀螺仪（点击切换曲线）")
        gl = QGridLayout(gyro_box)
        self.gyro_labels = []
        self.gyro_click_widgets = []
        for i in range(8):
            title = QLabel(f"陀螺仪{i+1}")
            title.setAlignment(Qt.AlignCenter)
            title.setStyleSheet("font-weight:bold;color:white;")
            gl.addWidget(title,0,i)
            lp=QLabel("俯仰"); lr=QLabel("横滚"); ly=QLabel("偏航")
            lax=QLabel("X"); lay=QLabel("Y"); laz=QLabel("Z")
            row_list = [lp,lr,ly,lax,lay,laz]
            for ridx,li in enumerate(row_list):
                li.setAlignment(Qt.AlignCenter)
                li.setStyleSheet(GYRO_CLICK_STYLE)
                li.setCursor(Qt.PointingHandCursor)
                li.mousePressEvent = lambda e,idx=i:self.select_gyro(idx)
                gl.addWidget(li, ridx+1, i)
            self.gyro_labels.append(row_list)
            self.gyro_click_widgets.append(row_list)
        main_layout.addWidget(gyro_box)

        # 曲线图区域：恢复原始大尺寸
        plot_box = QGroupBox("陀螺仪X/Y/Z加速度实时曲线")
        self.plot = pg.PlotWidget()
        self.plot.setBackground("#071f3a")
        # 增强网格样式 - 科幻发光效果
        self.plot.showGrid(x=True, y=True, alpha=0.4)
        self.plot.getPlotItem().getAxis('left').setPen(pg.mkPen('#60a5fa', width=1.5))
        self.plot.getPlotItem().getAxis('bottom').setPen(pg.mkPen('#60a5fa', width=1.5))
        self.plot.getPlotItem().getAxis('left').setTextPen(pg.mkPen('#C9E6FF', width=1))
        self.plot.getPlotItem().getAxis('bottom').setTextPen(pg.mkPen('#C9E6FF', width=1))
        self.plot.setYRange(-4, 4)
        self.plot.setMenuEnabled(False)
        self.plot.hideButtons()
        self.plot.setMouseEnabled(False, False)
        # 增强曲线样式 - 更粗的线条和发光效果
        self.cx = self.plot.plot(pen=pg.mkPen("#3b82f6", width=3))
        self.cy = self.plot.plot(pen=pg.mkPen("#10b981", width=3))
        self.cz = self.plot.plot(pen=pg.mkPen("#ef4444", width=3))
        plot_layout = QVBoxLayout(plot_box)
        plot_layout.addWidget(self.plot)
        plot_box.setMinimumHeight(250)  # 稍微增加高度以适应增强的视觉效果
        main_layout.addWidget(plot_box)

        # 日志区域：设置为原来的3倍高度
        log_box = QGroupBox("通信日志")
        log_lay = QVBoxLayout(log_box)
        self.log_edit = QTextEdit()
        self.log_edit.setReadOnly(True)
        # 关键：设置日志的最小高度为3倍（原约120 → 360）
        self.log_edit.setMinimumHeight(360)
        log_lay.addWidget(self.log_edit)
        main_layout.addWidget(log_box)

        scroll_area.setWidget(main_widget)
        self.select_gyro(0)

    def select_gyro(self, idx):
        self.selected_gyro = idx
        for i,ws in enumerate(self.gyro_click_widgets):
            style = SELECTED_GYRO_STYLE if i==idx else GYRO_CLICK_STYLE
            for w in ws:
                w.setStyleSheet(style)
        self.log(f"✅ 已切换显示陀螺仪{idx+1}曲线")

    def refresh_plot(self):
        buf = self.gyro_data_buffer[self.selected_gyro]
        self.cx.setData([v*3 for v in buf["ax"][-self.max_points:]])
        self.cy.setData([v*3 for v in buf["ay"][-self.max_points:]])
        self.cz.setData([v*3 for v in buf["az"][-self.max_points:]])

    def refresh_com_port(self):
        ports = [p.device for p in serial.tools.list_ports.comports()]
        self.cb_port1.clear(); self.cb_port1.addItems(ports)
        self.cb_port2.clear(); self.cb_port2.addItems(ports)

    def toggle_conn_main(self):
        if not self.worker_main:
            p = self.cb_port1.currentText()
            # 检查是否选择了COM口
            if not p:
                self.show_alert("连接失败", "未指定任何COM口连接。连接失败")
                return
            b = int(self.cb_baud1.currentText())
            self.worker_main = SerialWorker(p,b,CMD_MAIN,0)
            self.worker_main.sig_data.connect(self.up_main)
            self.worker_main.sig_log.connect(self.log)
            self.worker_main.sig_cmd_result.connect(self.on_cmd_result)
            self.worker_main.start()
            self.btn_conn1.setText("断开"); self.btn_conn1.setStyleSheet("background:#ef4444")
        else:
            self.worker_main.stop()
            self.worker_main.wait()
            self.worker_main = None
            self.btn_conn1.setText("连接主板"); self.btn_conn1.setStyleSheet("")

    def toggle_conn_gyro(self):
        if not self.worker_gyro:
            p = self.cb_port2.currentText()
            # 检查是否选择了COM口
            if not p:
                self.show_alert("连接失败", "未指定任何COM口连接。连接失败")
                return
            b = int(self.cb_baud2.currentText())
            sample_rate_text = self.cb_sample_rate.currentText()
            if sample_rate_text == "1Hz":
                sample_interval = 1.0
            elif sample_rate_text == "5Hz":
                sample_interval = 0.2
            elif sample_rate_text == "10Hz":
                sample_interval = 0.1
            else:
                sample_interval = 0.5
            self.worker_gyro = SerialWorker(p, b, CMD_GYRO, 1, sample_interval)
            self.worker_gyro.sig_data.connect(self.up_gyro)
            self.worker_gyro.sig_log.connect(self.log)
            self.worker_gyro.start()
            self.btn_conn2.setText("断开"); self.btn_conn2.setStyleSheet("background:#ef4444")
        else:
            self.worker_gyro.stop()
            self.worker_gyro.wait()
            self.worker_gyro = None
            self.btn_conn2.setText("连接陀螺仪板"); self.btn_conn2.setStyleSheet("")

    def up_main(self, d, idx):
        for k,v in self.strain_labels.items():
            v.setText(str(d[k]))
        for k,v in self.weather_labels.items():
            val = d[k]
            if isinstance(val,float):
                v.setText(f"{val:.2f}")
            else:
                v.setText(f"{val}")

    def up_gyro(self, glist, idx):
        for i,g in enumerate(glist):
            labs = self.gyro_labels[i]
            labs[0].setText(f"俯仰{g['pitch']:.1f}°")
            labs[1].setText(f"横滚{g['roll']:.1f}°")
            labs[2].setText(f"偏航{g['yaw']:.1f}°")
            labs[3].setText(f"X{g['ax']:.2f}G")
            labs[4].setText(f"Y{g['ay']:.2f}G")
            labs[5].setText(f"Z{g['az']:.2f}G")

            buf = self.gyro_data_buffer[i]
            buf["ax"].append(g["ax"])
            buf["ay"].append(g["ay"])
            buf["az"].append(g["az"])
            if len(buf["ax"])>self.max_points:
                buf["ax"].pop(0)
                buf["ay"].pop(0)
                buf["az"].pop(0)

            if self.last_z[i] is not None and abs(g['az'] - self.last_z[i]) > 0.1 and not self.alarm_on_flag:
                self.trigger_alarm()
            self.last_z[i] = g['az']
        self.refresh_plot()

    def trigger_alarm(self):
        if self.worker_main:
            self.worker_main.send_with_retry_async(ALARM_ON, attempts=5, delay=0.1)
            self.log("⚠️ Z轴突变 > 0.1G → 请求开启声光报警（异步）", True)

    def close_alarm_auto(self):
        if self.worker_main:
            self.worker_main.send_with_retry_async(ALARM_OFF, attempts=5, delay=0.1)
            self.log("ℹ️ 请求关闭声光报警（异步）", False)

    def send_motor_on(self):
        if self.worker_main:
            self.btn_motor_start.setEnabled(False)
            self.worker_main.send_with_retry_async(MOTOR_ON, attempts=5, delay=0.1)
            self.log("📤 请求启动振动电机（异步）")

    def send_motor_off(self):
        if self.worker_main:
            self.btn_motor_stop.setEnabled(False)
            self.worker_main.send_with_retry_async(MOTOR_OFF, attempts=5, delay=0.1)
            self.log("📤 请求关闭振动电机（异步）")

    def on_cmd_result(self, data, ok, resp):
        if resp:
            self.log(f"📥 控制应答: {hex_str(resp)}")
        if data == MOTOR_ON:
            if ok:
                self.btn_motor_start.setEnabled(False)
                self.btn_motor_stop.setEnabled(True)
                self.log("📤 振动电机 → 启动（确认）")
            else:
                self.btn_motor_start.setEnabled(True)
                self.log("❌ 振动电机 控制失败", True)
                self.show_alert("控制失败", "振动电机控制失败，请联系管理人员处理")
        elif data == MOTOR_OFF:
            if ok:
                self.btn_motor_stop.setEnabled(False)
                self.btn_motor_start.setEnabled(True)
                self.log("📤 振动电机 → 关闭（确认）")
            else:
                self.btn_motor_stop.setEnabled(True)
                self.log("❌ 振动电机 关闭失败", True)
                self.show_alert("控制失败", "振动电机控制失败，请联系管理人员处理")
        elif data == ALARM_ON:
            if ok:
                self.alarm_on_flag = True
                self.alarm_timer.start()
                self.log("⚠️ 声光报警 → 已确认开启", True)
            else:
                self.log("❌ 声光警报开启失败", True)
                self.show_alert("控制失败", "声光警报控制失败，请联系管理人员处理")
        elif data == ALARM_OFF:
            if ok:
                self.alarm_on_flag = False
                self.alarm_timer.stop()
                self.log("✅ 声光报警已自动关闭")
            else:
                self.log("❌ 声光警报关闭失败", True)
                self.show_alert("控制失败", "声光警报控制失败，请联系管理人员处理")

    def show_alert(self, title, text):
        mb = QMessageBox(self)
        mb.setIcon(QMessageBox.Critical)
        mb.setWindowTitle(title)
        mb.setText(text)
        mb.setStandardButtons(QMessageBox.Ok)
        mb.setModal(False)
        mb.setStyleSheet("""
            QMessageBox {
                background-color: #0f2047 !important;
                border: 3px solid #3b82f6 !important;
                border-radius: 12px !important;
                box-shadow: 0 0 25px rgba(59, 130, 246, 0.6) !important;
            }
            QMessageBox QLabel {
                color: #ffffff !important;
                font-size: 15px !important;
                font-weight: bold !important;
                background-color: transparent !important;
                padding: 15px !important;
                text-shadow: 0 0 10px rgba(255, 255, 255, 0.7) !important;
            }
            QMessageBox QPushButton {
                background-color: #66b3ff !important;
                color: #ffffff !important;
                border: 2px solid #3b82f6 !important;
                border-radius: 8px !important;
                padding: 10px 24px !important;
                font-size: 14px !important;
                font-weight: bold !important;
                min-width: 90px !important;
                box-shadow: 0 0 15px rgba(102, 179, 255, 0.5) !important;
                text-shadow: 0 0 8px rgba(255, 255, 255, 0.6) !important;
            }
            QMessageBox QPushButton:hover {
                background-color: #4da6ff !important;
                border: 2px solid #60a5fa !important;
                box-shadow: 0 0 25px rgba(96, 165, 250, 0.7) !important;
                transform: scale(1.05) !important;
            }
        """)
        mb.show()
        self._active_msgboxes.append(mb)
        def _on_finished():
            try:
                self._active_msgboxes.remove(mb)
            except ValueError:
                pass
        mb.finished.connect(_on_finished)

    def log(self, msg, err=False):
        t = time.strftime("%H:%M:%S")
        color = "#f87171" if err else "#22d3ee"
        self.log_edit.append(f"<span style='color:{color}'>[{t}] {msg}</span>")
        
    def show_startup_info(self):
        """显示启动信息"""
        url_status = "✅ 已配置" if VERSION_CHECK_URL else "⚠️ 未配置"
        self.log(f"🚀 程序启动 - 版本: v{CURRENT_VERSION}", False)
        self.log(f"📡 版本检查: {'启用' if APP_CONFIG.get('check_on_startup', True) else '禁用'} ({url_status})", False)

    def on_sample_rate_changed(self, text):
        if self.worker_gyro is not None:
            self.worker_gyro.stop()
            self.worker_gyro.wait()
            self.worker_gyro = None
            self.btn_conn2.setText("连接陀螺仪板")
            self.btn_conn2.setStyleSheet("")
            self.log(f"ℹ️ 采样率已更改为{text}，自动断开连接", False)

    def check_for_updates(self):
        """检查是否有新版本"""
        if not VERSION_CHECK_URL:
            return

        self.update_checker = UpdateChecker(CURRENT_VERSION, VERSION_CHECK_URL)
        self.update_checker.update_available.connect(self.on_update_available)
        self.update_checker.no_update.connect(self.on_no_update)
        self.update_checker.check_error.connect(self.on_check_error)
        self.update_checker.start()

    def on_update_available(self, version, notes, download_url):
        """发现新版本"""
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Information)
        msg.setWindowTitle("发现新版本")
        msg.setText(f"发现新版本 v{version}！")
        msg.setInformativeText(f"当前版本：v{CURRENT_VERSION}\n\n更新说明：\n{notes}")
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg.button(QMessageBox.Yes).setText("立即更新")
        msg.button(QMessageBox.No).setText("稍后再说")
        msg.setStyleSheet("""
            QMessageBox {
                background-color: #0f2047 !important;
                border: 3px solid #3b82f6 !important;
                border-radius: 12px !important;
                box-shadow: 0 0 25px rgba(59, 130, 246, 0.6) !important;
            }
            QMessageBox QLabel {
                color: #ffffff !important;
                font-size: 14px !important;
                background-color: transparent !important;
                padding: 10px !important;
            }
            QMessageBox QPushButton {
                background-color: #66b3ff !important;
                color: #ffffff !important;
                border: 2px solid #3b82f6 !important;
                border-radius: 8px !important;
                padding: 8px 20px !important;
                font-size: 13px !important;
                font-weight: bold !important;
                min-width: 90px !important;
            }
            QMessageBox QPushButton:hover {
                background-color: #4da6ff !important;
                border: 2px solid #60a5fa !important;
            }
        """)
        
        reply = msg.exec_()
        if reply == QMessageBox.Yes:
            self.download_update(version, download_url)

    def on_no_update(self):
        """当前已是最新版本"""
        pass  # 静默处理，不弹窗

    def on_check_error(self, error_msg):
        """检查更新出错"""
        self.log(f"❌ {error_msg}", True)

    def download_update(self, version, download_url):
        """下载更新"""
        if not download_url:
            self.show_alert("更新失败", "未提供下载链接，请联系管理员")
            return

        # 创建下载进度对话框
        self.download_dialog = QDialog(self)
        self.download_dialog.setWindowTitle("正在下载更新")
        self.download_dialog.setModal(True)
        self.download_dialog.resize(450, 200)
        self.download_dialog.setStyleSheet("QDialog { background-color: #0f2047; border: 2px solid #3b82f6; border-radius: 10px; }")
        
        layout = QVBoxLayout(self.download_dialog)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 版本信息
        version_label = QLabel(f"正在下载 v{version}...")
        version_label.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: bold;")
        version_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(version_label)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #0a1929;
                border: 2px solid #1e3a8a;
                border-radius: 5px;
                text-align: center;
                color: #ffffff;
            }
            QProgressBar::chunk {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0EA5E9, stop:1 #3b82f6);
                border-radius: 3px;
            }
        """)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)
        
        # 状态标签
        self.status_label = QLabel("准备下载...")
        self.status_label.setStyleSheet("color: #cbd5e1; font-size: 12px;")
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)
        
        # 取消按钮
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.cancel_download)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #ef4444;
                color: #ffffff;
                border: 2px solid #dc2626;
                border-radius: 6px;
                padding: 8px 20px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #dc2626;
            }
        """)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        # 准备下载 - 使用固定的 .exe 文件名
        import tempfile
        self.pending_update_file = os.path.join(tempfile.gettempdir(), f"update_v{version}.exe")
        
        self.download_worker = DownloadWorker(download_url, self.pending_update_file)
        self.download_worker.progress.connect(self.on_download_progress)
        self.download_worker.finished.connect(self.on_download_finished)
        self.download_worker.error.connect(self.on_download_error)
        self.download_worker.start()
        
        self.download_dialog.exec_()

    def on_download_progress(self, downloaded, total):
        """更新下载进度"""
        if total > 0:
            percent = int((downloaded / total) * 100)
            self.progress_bar.setValue(percent)
            downloaded_mb = downloaded / (1024 * 1024)
            total_mb = total / (1024 * 1024)
            self.status_label.setText(f"已下载：{downloaded_mb:.2f} MB / {total_mb:.2f} MB")
        else:
            self.status_label.setText(f"已下载：{downloaded / (1024 * 1024):.2f} MB")

    def on_download_finished(self, file_path):
        """下载完成"""
        self.download_dialog.close()
        
        # 提示用户安装更新
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Information)
        msg.setWindowTitle("下载完成")
        msg.setText("✅ 更新已下载完成！")
        msg.setInformativeText("程序将自动关闭并安装更新，安装完成后请重新启动程序。")
        msg.setStandardButtons(QMessageBox.Ok)
        msg.button(QMessageBox.Ok).setText("立即安装")
        msg.setStyleSheet("""
            QMessageBox {
                background-color: #0f2047 !important;
                border: 3px solid #10b981 !important;
                border-radius: 12px !important;
                box-shadow: 0 0 25px rgba(16, 185, 129, 0.6) !important;
            }
            QMessageBox QLabel {
                color: #ffffff !important;
                font-size: 14px !important;
                background-color: transparent !important;
                padding: 10px !important;
            }
            QMessageBox QPushButton {
                background-color: #10b981 !important;
                color: #ffffff !important;
                border: 2px solid #059669 !important;
                border-radius: 8px !important;
                padding: 8px 20px !important;
                font-size: 13px !important;
                font-weight: bold !important;
                min-width: 90px !important;
            }
            QMessageBox QPushButton:hover {
                background-color: #059669 !important;
            }
        """)
        
        if msg.exec_() == QMessageBox.Ok:
            self.install_update(file_path)

    def on_download_error(self, error_msg):
        """下载出错"""
        if hasattr(self, 'download_dialog') and self.download_dialog.isVisible():
            self.download_dialog.close()
        self.show_alert("下载失败", error_msg)

    def cancel_download(self):
        """取消下载"""
        if self.download_worker:
            self.download_worker.stop()
            self.download_dialog.close()

    def install_update(self, update_file):
        """安装更新"""
        if not os.path.exists(update_file):
            self.show_alert("安装失败", "更新文件不存在")
            return

        try:
            # 获取当前程序路径
            current_exe = sys.executable if getattr(sys, 'frozen', False) else sys.argv[0]
            
            # 创建批处理脚本
            bat_file = os.path.join(os.path.dirname(current_exe), "install_update.bat")
            with open(bat_file, 'w', encoding='gbk') as f:
                f.write('@echo off\n')
                f.write('echo 正在安装更新，请稍候...\n')
                f.write('timeout /t 2 /nobreak >nul\n')
                f.write(f'copy /y "{update_file}" "{current_exe}"\n')
                f.write(f'start "" "{current_exe}"\n')
                f.write('del "%~f0"\n')
                f.write('exit\n')
            
            # 执行批处理脚本并退出当前程序
            subprocess.Popen(f'cmd /c start "" "{bat_file}"', shell=True)
            QApplication.instance().quit()
            
        except Exception as e:
            self.show_alert("安装失败", f"更新安装失败：{str(e)}")

    def show_about(self):
        """显示关于对话框，包含版本信息和更新历史"""
        dialog = QDialog(self)
        dialog.setWindowTitle("关于 桥梁模型箱 485综合采集上位机")
        dialog.setModal(True)
        dialog.resize(650, 550)
        dialog.setStyleSheet("""
            QDialog {
                background-color: #0f2047;
                border: 3px solid #3b82f6;
                border-radius: 12px;
            }
        """)
        
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # 标题区域
        title_label = QLabel("🌉 桥梁模型箱 485综合采集上位机")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("""
            font-size: 20px;
            font-weight: bold;
            color: #ffffff;
            text-shadow: 0 0 15px rgba(59, 130, 246, 0.8);
            padding: 10px;
        """)
        layout.addWidget(title_label)
        
        # 版本信息
        version_label = QLabel(f"当前版本: v{CURRENT_VERSION}")
        version_label.setAlignment(Qt.AlignCenter)
        version_label.setStyleSheet("""
            font-size: 16px;
            font-weight: bold;
            color: #60a5fa;
            text-shadow: 0 0 10px rgba(96, 165, 250, 0.6);
            padding: 5px;
        """)
        layout.addWidget(version_label)
        
        # 分割线
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("background-color: #3b82f6;")
        layout.addWidget(line)
        
        # 更新历史标题
        history_title = QLabel("📋 版本更新历史")
        history_title.setStyleSheet("""
            font-size: 16px;
            font-weight: bold;
            color: #ffffff;
            text-shadow: 0 0 8px rgba(255, 255, 255, 0.5);
            padding: 5px;
        """)
        layout.addWidget(history_title)
        
        # 版本历史滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                background-color: #081827;
                border: 2px solid #1e3a8a;
                border-radius: 8px;
            }
        """)
        
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(15, 15, 15, 15)
        scroll_layout.setSpacing(20)
        
        # 遍历版本历史
        for idx, ver_info in enumerate(VERSION_HISTORY):
            version_card = QWidget()
            version_card.setStyleSheet("""
                QWidget {
                    background-color: #0a1929;
                    border: 2px solid #1e3a8a;
                    border-radius: 8px;
                    padding: 10px;
                }
            """)
            
            card_layout = QVBoxLayout(version_card)
            card_layout.setSpacing(8)
            
            # 版本号和日期
            ver_header = QLabel(f"版本 {ver_info['version']}  |  {ver_info['date']}")
            ver_header.setStyleSheet("""
                font-size: 15px;
                font-weight: bold;
                color: #60a5fa;
                text-shadow: 0 0 8px rgba(96, 165, 250, 0.5);
            """)
            card_layout.addWidget(ver_header)
            
            # 更新标题
            ver_title = QLabel(f"🎯 {ver_info['title']}")
            ver_title.setStyleSheet("""
                font-size: 14px;
                font-weight: bold;
                color: #ffffff;
                padding-left: 10px;
            """)
            card_layout.addWidget(ver_title)
            
            # 更新内容列表
            changes_text = "\n".join([f"  • {change}" for change in ver_info['changes']])
            changes_label = QLabel(changes_text)
            changes_label.setWordWrap(True)
            changes_label.setStyleSheet("""
                font-size: 13px;
                color: #cbd5e1;
                padding-left: 10px;
                line-height: 1.5;
            """)
            card_layout.addWidget(changes_label)
            
            scroll_layout.addWidget(version_card)
        
        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        scroll.setMinimumHeight(250)
        layout.addWidget(scroll)
        
        # 确定按钮
        btn_ok = QPushButton("确定")
        btn_ok.clicked.connect(dialog.close)
        btn_ok.setStyleSheet("""
            QPushButton {
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #0EA5E9, stop:1 #0284C7);
                color: #ffffff;
                border: 2px solid #3b82f6;
                border-radius: 8px;
                padding: 10px 40px;
                font-size: 14px;
                font-weight: bold;
                box-shadow: 0 0 12px rgba(14, 165, 233, 0.4);
                text-shadow: 0 0 8px rgba(255, 255, 255, 0.6);
            }
            QPushButton:hover {
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #3b82f6, stop:1 #0b79b0);
                border: 2px solid #60a5fa;
                box-shadow: 0 0 20px rgba(96, 165, 250, 0.6);
            }
        """)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(btn_ok)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        dialog.exec_()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())