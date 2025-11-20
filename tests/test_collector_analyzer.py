
import threading
import time
import json
import socket
from main import Analyzer, run_collector

def test_collector_to_analyzer_communication():

    analyzer = Analyzer(port=9999, window=10, z_threshold=3.0)
    analyzer_thread = threading.Thread(target=analyzer.start, daemon=True)
    analyzer_thread.start()
    time.sleep(1)


    collector_thread = threading.Thread(
        target=run_collector,
        args=("127.0.0.1", 9999, 0.1, ""),
        daemon=True
    )
    collector_thread.start()


    time.sleep(3)

    assert len(analyzer.stats) > 0

    analyzer.stop_flag.set()
    time.sleep(1)
    print("Интеграция Collector ↔ Analyzer — УСПЕШНО")