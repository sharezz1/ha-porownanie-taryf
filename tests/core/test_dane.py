from datetime import date, datetime

from custom_components.porownanie_taryf.core import TZ
from tests.dane import godziny, wrzesien


def test_wrzesien():
    w = wrzesien()
    assert len(w) == 720
    assert w[0].start_local == datetime(2026, 9, 1, 0, tzinfo=TZ)
    assert w[-1].start_local.hour == 23 and w[-1].start_local.day == 30


def test_dzien_dst_ma_25_godzin():
    assert godziny(datetime(2026, 10, 25, tzinfo=TZ), 25)[-1].start_local.date() == date(2026, 10, 25)
