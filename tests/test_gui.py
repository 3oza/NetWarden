
import pytest
from PyQt6.QtWidgets import QApplication
from main import MainWindow

@pytest.mark.qt
def test_gui_starts_and_autoconnects(qapp, qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)


    qtbot.waitUntil(
        lambda: "Analyzer слушает" in window.log.toPlainText(),
        timeout=15000
    )
    qtbot.waitUntil(
        lambda: "Collector подключён" in window.log.toPlainText(),
        timeout=15000
    )

    assert window.analyzer_thread.is_alive()
    assert window.collector_thread.is_alive()

    qtbot.waitUntil(lambda: window.table.rowCount() > 0, timeout=20000)
    assert window.table.rowCount() > 0

    print("GUI + автозапуск — УСПЕШНО")