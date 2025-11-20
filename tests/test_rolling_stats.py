
import pytest
from main import RollingStats 

def test_rolling_mean_and_std():
    rs = RollingStats(window=5)
    for x in [10, 20, 30, 40, 50]:
        rs.add(x)
    assert rs.mean() == 30.0
    assert pytest.approx(rs.std(), 0.01) == 15.811388

def test_window_limit():
    rs = RollingStats(window=3)
    for x in [1, 2, 3, 4, 5]:
        rs.add(x)
    assert len(rs.window) == 3
    assert rs.mean() == 4.0  # 3, 4, 5

def test_edge_cases():
    rs = RollingStats(10)
    assert rs.mean() == 0.0
    assert rs.std() == 0.0
    rs.add(100)
    assert rs.mean() == 100.0
    assert rs.std() == 0.0