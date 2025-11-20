
import sys
import socket
import threading
import time
import json
import psutil
from collections import deque
from datetime import datetime

from PyQt6.QtWidgets import *
from PyQt6.QtCore import QTimer, Qt, pyqtSignal, QObject
from PyQt6.QtGui import QFont

from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import qdarkstyle


stats = {}
history = {}
lock = threading.Lock()


class Signals(QObject):
    update = pyqtSignal()
    log = pyqtSignal(str, str) 


signals = Signals()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("NetWarden — Автозапуск (всё работает сразу)")
        self.resize(1200, 700)


        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)


        left = QGroupBox("Статус и лог")
        left.setMaximumWidth(380)
        vbox = QVBoxLayout(left)

        self.label = QLabel("Запуск Analyzer и Collector...")
        self.label.setStyleSheet("font-size: 16px; color: yellow;")
        vbox.addWidget(self.label)

        self.log = QTextEdit()
        self.log.setFont(QFont("Consolas", 10))
        self.log.setReadOnly(True)
        vbox.addWidget(self.log)

        right = QVBoxLayout()

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Хост", "Интерфейс", "Трафик", "Z-score", "Статус"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        right.addWidget(self.table)

        self.figure = Figure(facecolor="#1e1e1e")
        self.canvas = FigureCanvas(self.figure)
        self.ax = self.figure.add_subplot(111)
        self.ax.set_facecolor("#2b2b2b")
        right.addWidget(self.canvas)

        layout.addWidget(left)
        layout.addLayout(right)


        signals.log.connect(self.add_log)
        signals.update.connect(self.refresh_ui)


        QTimer.singleShot(1000, self.auto_start)

    def add_log(self, text, color="white"):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log.append(f'<span style="color:{color};">[{ts}] {text}</span>')
        self.log.verticalScrollBar().setValue(self.log.verticalScrollBar().maximum())

    def auto_start(self):
        threading.Thread(target=start_analyzer, daemon=True).start()
        time.sleep(1)
        threading.Thread(target=start_collector, daemon=True).start()

    def refresh_ui(self):
        with lock:
            self.table.setRowCount(len(stats))
            row = 0
            for (host, iface), data in stats.items():
                rs = data["rs"]
                hist = history.get((host, iface), deque())
                value = hist[-1] if hist else 0
                mean = rs.mean()
                std = rs.std() if rs.std() > 0 else 1
                z = (value - mean) / std

                status = "АНОМАЛИЯ!" if abs(z) > 3 else "Норма"
                color = "red" if abs(z) > 3 else "green"

                self.table.setItem(row, 0, QTableWidgetItem(host))
                self.table.setItem(row, 1, QTableWidgetItem(iface))
                self.table.setItem(row, 2, QTableWidgetItem(f"{value/1e6:.2f} MB/s"))
                self.table.setItem(row, 3, QTableWidgetItem(f"{z:+.2f}"))
                item = QTableWidgetItem(status)
                item.setForeground(Qt.GlobalColor.red if color == "red" else Qt.GlobalColor.green)
                self.table.setItem(row, 4, item)
                row += 1

            # График
            self.ax.clear()
            now = time.time()
            for (host, iface), data in history.items():
                if len(data) < 2: continue
                times = [now - (len(data) - i - 1) for i in range(len(data))]
                values = [v / 1e6 for v in data]
                self.ax.plot(times, values, label=f"{host} • {iface}", linewidth=2)

            self.ax.set_title("Трафик в реальном времени", color="white")
            self.ax.set_ylabel("MB/s", color="white")
            self.ax.grid(True, alpha=0.3)
            if history:
                self.ax.legend(fontsize=9)
            self.canvas.draw()


def start_analyzer():
    server = socket.socket()
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server.bind(("127.0.0.1", 9000))
        server.listen(5)
        signals.log.emit("Analyzer запущен на 127.0.0.1:9000", "lime")
    except Exception as e:
        signals.log.emit(f"ОШИБКА Analyzer: {e}", "red")
        return

    while True:
        try:
            conn, addr = server.accept()
            threading.Thread(target=handle_client, args=(conn,), daemon=True).start()
        except:
            break


def handle_client(conn):
    buf = b""
    with conn:
        while True:
            try:
                data = conn.recv(4096)
                if not data: break
                buf += data
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    if line.strip():
                        try:
                            m = json.loads(line)
                            process_metric(m)
                        except:
                            pass
            except:
                break


def process_metric(m):
    host = m["host"]
    iface = m["iface"]
    key = (host, iface)
    value = m.get("total_bps", m.get("bytes_tx_s", 0) + m.get("bytes_rx_s", 0))

    with lock:
        if key not in stats:
            stats[key] = {"rs": RollingStats(60)}
            history[key] = deque(maxlen=300)
        rs = stats[key]["rs"]
        rs.add(value)
        history[key].append(value)

        std = rs.std()
        z = (value - rs.mean()) / std if std > 0 else 0
        if abs(z) > 3:
            signals.log.emit(f"АНОМАЛИЯ! {host} {iface}: {value/1e6:.1f} MB/s (z={z:+.2f})", "red")

    signals.update.emit()


def start_collector():
    signals.log.emit("Collector запущен (локально)", "cyan")
    hostname = socket.gethostname()
    prev = psutil.net_io_counters(pernic=True)
    prev_ts = time.time()

    while True:
        try:
            sock = socket.create_connection(("127.0.0.1", 9000), timeout=5)
            signals.log.emit("Подключено к Analyzer!", "green")

            while True:
                time.sleep(1)
                now = time.time()
                cur = psutil.net_io_counters(pernic=True)
                dt = now - prev_ts if now > prev_ts else 1

                lines = []
                for iface, c in cur.items():
                    p = prev.get(iface)
                    if not p: continue
                    total = (c.bytes_sent - p.bytes_sent + c.bytes_recv - p.bytes_recv) / dt
                    if total < 1000: continue 
                    lines.append(json.dumps({
                        "host": hostname,
                        "iface": iface,
                        "total_bps": total,
                        "bytes_tx_s": (c.bytes_sent - p.bytes_sent) / dt,
                        "bytes_rx_s": (c.bytes_recv - p.bytes_recv) / dt,
                    }) + "\n")

                if lines:
                    try:
                        sock.sendall("".join(lines).encode())
                    except:
                        break

                prev, prev_ts = cur, now

        except Exception as e:
            signals.log.emit(f"Collector: потеряно соединение, переподключаюсь...", "yellow")
            time.sleep(3)


class RollingStats:
    def __init__(self, window=60):
        self.window = deque(maxlen=window)
        self.sum = self.sumsq = 0.0

    def add(self, x):
        if len(self.window) == self.window.maxlen:
            old = self.window.popleft()
            self.sum -= old
            self.sumsq -= old * old
        self.window.append(x)
        self.sum += x
        self.sumsq += x * x

    def mean(self):
        return self.sum / len(self.window) if self.window else 0

    def std(self):
        n = len(self.window)
        if n < 2: return 0
        var = (self.sumsq - self.sum**2 / n) / (n - 1)
        return max(var, 0) ** 0.5


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet(qdarkstyle.load_stylesheet_pyqt6())

    window = MainWindow()
    window.show()

    timer = QTimer()
    timer.timeout.connect(lambda: signals.update.emit())
    timer.start(1000)


    sys.exit(app.exec())
