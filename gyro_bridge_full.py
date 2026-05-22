import sys
import time
import struct
import serial
import serial.tools.list_ports
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
import pyqtgraph as pg
import threading

# ===================== CRC16 校验（修正字节序，与Modbus RTU完全一致） =====================
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
    # 关键修正：Modbus CRC 是 低字节在前，高字节在后
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
QMainWindow{background-color: #0F172A;}
QGroupBox{color: #E2E8F0;font-size:14px;font-weight:bold;border:1px solid #334155;border-radius:8px;margin-top:12px;padding-top:15px;}
QGroupBox::title{subcontrol-origin: margin;left:15px;top:5px;}
QLabel{color:#CBD5E1;font-size:13px;}
QPushButton{background-color:#0EA5E9;color:#FFF;border:none;border-radius:6px;padding:8px 20px;font-size:13px;}
QPushButton:hover{background-color:#0284C7;}
QPushButton:disabled{background-color:#475569;color:#999;}
QComboBox{background-color:#1E293B;color:#F1F5F9;border:1px solid #475569;border-radius:6px;padding:6px 10px;}
QComboBox QAbstractItemView{background-color:#1E293B;color:#F1F5F9;selection-background-color:#0EA5E9;}
QTextEdit{background-color:#1E293B;color:#22D3EE;font-family:Consolas;font-size:12px;border:1px solid #334155;border-radius:6px;}
/* 弹窗科幻风格样式 */
QMessageBox{
    background-color: #0f2047 !important;
    border: 2px solid #3b82f6 !important;
    border-radius: 10px !important;
}
QMessageBox QLabel{
    color: #ffffff !important;
    font-size: 14px !important;
    background-color: transparent !important;
}
QMessageBox QPushButton{
    background-color: #66b3ff !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 5px !important;
    padding: 8px 20px !important;
    font-size: 13px !important;
    min-width: 80px !important;
}
QMessageBox QPushButton:hover{
    background-color: #4da6ff !important;
}
"""

DATA_LABEL_STYLE = """
QLabel{
    background-color:#1E293B;
    color:#22D3EE;
    font-size:15px;
    font-weight:bold;
    padding:6px 4px;
    border:1px solid #334155;
    border-radius:6px;
    min-width:110px;
}
"""

GYRO_CLICK_STYLE = """
QLabel{
    background-color:#1E293B;
    color:#22D3EE;
    font-size:15px;
    font-weight:bold;
    padding:6px 4px;
    border:1px solid #334155;
    border-radius:6px;
}
QLabel:hover{background-color:#2a4365;border:1px solid #3b82f6;}
"""

SELECTED_GYRO_STYLE = """
QLabel{
    background-color:#3b82f6;
    color:white;
    font-size:15px;
    font-weight:bold;
    padding:6px 4px;
    border:1px solid #60a5fa;
    border-radius:6px;
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
                    # 在通信日志中打印收到的原始字节（十六进制）
                    self.sig_log.emit(f"📥 收到帧: {hex_str(buf)}", False)

                if len(buf) < 8:
                    self.sig_log.emit(f"⚠️ 数据过短，丢弃", True)
                    continue

                # CRC 校验（已修正字节序）
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

        # 气象顺序：风速 → 风力 → 风向档 → 风向角度 → 湿度 → 温度 → ...
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
        """
        发送并重试：每次写入后读取与发送帧等长的应答，若应答与发送帧完全相同则视为成功。
        该函数可在任意线程调用；对串口访问使用 ser_lock 保护。
        最终通过 sig_cmd_result 发回结果（data, bool, resp_bytes）。
        """
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
        """在独立线程中执行 send_with_retry，避免阻塞调用线程（通常是主线程）。"""
        t = threading.Thread(target=self.send_with_retry, args=(data, attempts, delay), daemon=True)
        t.start()

    def stop(self):
        self.running = False

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

        self.init_ui()
        self.refresh_com_port()

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(20,20,20,20)
        main_layout.setSpacing(12)

        top_layout = QHBoxLayout()
        g1 = QGroupBox("模型箱主板 地址0x01")
        l1 = QHBoxLayout(g1)
        self.cb_port1 = QComboBox()
        self.cb_baud1 = QComboBox()
        self.cb_baud1.addItems(["9600","115200"])
        self.cb_baud1.setCurrentText("115200")
        self.btn_conn1 = QPushButton("连接主板")
        self.btn_conn1.clicked.connect(self.toggle_conn_main)
        l1.addWidget(QLabel("COM:")); l1.addWidget(self.cb_port1)
        l1.addWidget(QLabel("波特率:")); l1.addWidget(self.cb_baud1)
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
        self.sample_rate_tip.setStyleSheet("color: #64748b; font-size: 11px;")
        self.btn_conn2 = QPushButton("连接陀螺仪板")
        self.btn_conn2.clicked.connect(self.toggle_conn_gyro)
        l2.addWidget(QLabel("COM:")); l2.addWidget(self.cb_port2)
        l2.addWidget(QLabel("波特率:")); l2.addWidget(self.cb_baud2)
        l2.addWidget(QLabel("采样率:")); l2.addWidget(self.cb_sample_rate)
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

        plot_box = QGroupBox("陀螺仪X/Y/Z加速度实时曲线")
        self.plot = pg.PlotWidget()
        self.plot.setBackground("#1E293B")
        self.plot.showGrid(x=True,y=True)
        self.plot.setYRange(-4,4)
        self.plot.setMenuEnabled(False)
        self.plot.hideButtons()
        self.plot.setMouseEnabled(False,False)
        self.cx = self.plot.plot(pen=pg.mkPen("#3b82f6",width=2))
        self.cy = self.plot.plot(pen=pg.mkPen("#10b981",width=2))
        self.cz = self.plot.plot(pen=pg.mkPen("#ef4444",width=2))
        plot_layout = QVBoxLayout(plot_box)
        plot_layout.addWidget(self.plot)
        main_layout.addWidget(plot_box)

        log_box = QGroupBox("通信日志")
        log_lay = QVBoxLayout(log_box)
        self.log_edit = QTextEdit()
        self.log_edit.setReadOnly(True)
        log_lay.addWidget(self.log_edit)
        main_layout.addWidget(log_box)

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
            b = int(self.cb_baud2.currentText())
            # 根据选择的采样率设置间隔时间
            sample_rate_text = self.cb_sample_rate.currentText()
            if sample_rate_text == "1Hz":
                sample_interval = 1.0
            elif sample_rate_text == "5Hz":
                sample_interval = 0.2
            elif sample_rate_text == "10Hz":
                sample_interval = 0.1
            else:
                sample_interval = 0.5  # 默认值
            
            self.worker_gyro = SerialWorker(p, b, CMD_GYRO, 1, sample_interval)
            self.worker_gyro.sig_data.connect(self.up_gyro)
            self.worker_gyro.sig_log.connect(self.log)
            self.worker_gyro.start()
            self.btn_conn2.setText("断开"); self.btn_conn2.setStyleSheet("background:#ef4444")
        else:
            self.worker_gyro.stop()
            self.worker_gyro.wait()
            self.worker_gyro = None
            self.btn_conn2.setText("连接陀螺仪"); self.btn_conn2.setStyleSheet("")

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
            # 发起异步请求，等待 on_cmd_result 处理结果回调
            self.worker_main.send_with_retry_async(ALARM_ON, attempts=5, delay=0.1)
            self.log("⚠️ Z轴突变 > 0.1G → 请求开启声光报警（异步）", True)

    def close_alarm_auto(self):
        if self.worker_main:
            self.worker_main.send_with_retry_async(ALARM_OFF, attempts=5, delay=0.1)
            self.log("ℹ️ 请求关闭声光报警（异步）", False)

    def send_motor_on(self):
        if self.worker_main:
            # 发起异步请求，等待 on_cmd_result 处理结果回调
            # 暂时禁用启动按钮以防重复点击
            self.btn_motor_start.setEnabled(False)
            self.worker_main.send_with_retry_async(MOTOR_ON, attempts=5, delay=0.1)
            self.log("📤 请求启动振动电机（异步）")

    def send_motor_off(self):
        if self.worker_main:
            # 暂时禁用关闭按钮以防重复点击
            self.btn_motor_stop.setEnabled(False)
            self.worker_main.send_with_retry_async(MOTOR_OFF, attempts=5, delay=0.1)
            self.log("📤 请求关闭振动电机（异步）")

    def on_cmd_result(self, data, ok, resp):
        """
        处理串口命令异步结果：根据命令和成功/失败状态更新界面或弹窗。
        使用非模态、主线程显示的对话框以避免阻塞。
        同时在通信日志打印收到的应答帧（十六进制）。
        """
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
        """在主线程以非模态方式显示错误提示，避免阻塞事件循环。"""
        mb = QMessageBox(self)
        mb.setIcon(QMessageBox.Critical)
        mb.setWindowTitle(title)
        mb.setText(text)
        mb.setStandardButtons(QMessageBox.Ok)
        mb.setModal(False)
        
        # 设置弹窗样式符合科幻风格
        mb.setStyleSheet("""
            QMessageBox {
                background-color: #0f2047 !important;
                border: 2px solid #3b82f6 !important;
                border-radius: 10px !important;
                box-shadow: 0 0 20px rgba(0, 0, 0, 0.5) !important;
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
                border: none !important;
                border-radius: 5px !important;
                padding: 8px 20px !important;
                font-size: 13px !important;
                min-width: 80px !important;
            }
            QMessageBox QPushButton:hover {
                background-color: #4da6ff !important;
            }
        """)
        
        mb.show()
        # 保持引用防止被回收
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

    def on_sample_rate_changed(self, text):
        """当采样率更改时，如果已连接陀螺仪，则自动断开"""
        if self.worker_gyro is not None:
            # 自动断开当前连接
            self.worker_gyro.stop()
            self.worker_gyro.wait()
            self.worker_gyro = None
            self.btn_conn2.setText("连接陀螺仪板")
            self.btn_conn2.setStyleSheet("")
            self.log(f"ℹ️ 采样率已更改为{text}，自动断开连接", False)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())