import warnings

import pytest
from aiohttp.web_exceptions import NotAppKeyWarning


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture(autouse=True)
def _zaleznosci_manifestu(hass):
    """Zależności z manifestu (`frontend`, `http`, `panel_custom`) w testach.

    Pakietu home-assistant-frontend nie ma w środowisku testowym, więc `frontend` i `panel_custom` oznaczamy jako
    gotowe (`async_register_panel` działa na samym hass.data). `http` ustawia się naprawdę, bo serwuje panel.js;
    jego kod HA używa kluczy `str` w aiohttp.Application, co pod `-W error` jest wyjątkiem, więc to ostrzeżenie ignorujemy.
    """
    for d in ("frontend", "panel_custom"):
        hass.config.components.add(d)
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=NotAppKeyWarning)
        yield
