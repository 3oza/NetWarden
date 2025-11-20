
from main import RollingStats

def test_zscore_anomaly_detection():
    rs = RollingStats(20)

    for _ in range(20):
        rs.add(1000)  # 1 MB/s — норма


    rs.add(15000)  # 15 MB/s
    z = (15000 - rs.mean()) / rs.std()
    assert abs(z) > 8.0  # сильная аномалия


    rs.add(20000)
    z2 = (20000 - rs.mean()) / rs.std()
    assert z2 > z