"""Coordinator: godziny w magazynie HA, odświeżanie z API Pstryk, przeliczenie okresu bez API (spec §6)."""

from datetime import date, datetime, timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .core import HourlyReading
from .core.presety import Konfiguracja, zbuduj_konfiguracje
from .core.scenariusz import Wynik, domyslna_data, policz, rozwiaz_okres
from .sources.pstryk import (
    PstrykAuthError,
    PstrykClient,
    PstrykEndpointError,
    PstrykError,
    PstrykRateLimitError,
    do_magazynu,
    z_magazynu,
)

_LOGGER = logging.getLogger(__name__)

ODSWIEZANIE = timedelta(hours=6)
BACKFILL = timedelta(days=730)
NAKLADKA = timedelta(hours=48)  # korekty OSD z ostatnich dób nadpisują stare godziny
MIN_RETRY_AFTER = 60  # API potrafi odesłać Retry-After: 0
ISSUE_ENDPOINT = "endpoint_zmieniony"

type TaryfyConfigEntry = ConfigEntry[TaryfyCoordinator]


class TaryfyCoordinator(DataUpdateCoordinator[Wynik | None]):
    """`data` to wynik dla wybranego okresu; None = zakres z końcem przed datą."""

    config_entry: TaryfyConfigEntry

    def __init__(self, hass: HomeAssistant, entry: TaryfyConfigEntry) -> None:
        super().__init__(hass, _LOGGER, config_entry=entry, name=DOMAIN, update_interval=ODSWIEZANIE)
        self.konf: Konfiguracja = zbuduj_konfiguracje(entry.data, entry.options)
        self._klient = PstrykClient(async_get_clientsession(hass), entry.data[CONF_API_KEY])
        self._store: Store[dict] = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}.hourly")
        self._godziny: dict[str, list] = {}  # klucz godziny UTC -> wartości, jak w do_magazynu
        self.odczyty: list[HourlyReading] = []
        self.rodzaj = "miesiac"
        self.dzien: date = domyslna_data(dt_util.now().date())
        self.koniec: date | None = None
        self.dane_z: datetime | None = None  # ostatnie udane pobranie z API
        self._nie_przed: datetime | None = None  # 429: bez zapytań do tej chwili

    async def wczytaj_magazyn(self) -> None:
        dane = await self._store.async_load() or {}
        self._godziny = dane.get("godziny", {})
        self.odczyty = z_magazynu(self._godziny)
        self.dane_z = dt_util.parse_datetime(dane["dane_z"]) if dane.get("dane_z") else None

    def przelicz(self) -> Wynik | None:
        okres = rozwiaz_okres(self.rodzaj, self.dzien, self.koniec)
        # ponytail: policz biegnie w pętli zdarzeń (~20 ms na rok danych); cache agregatów miesięcznych, gdy wolne hosty zgłoszą problem
        return policz(self.odczyty, *okres, self.konf) if okres else None

    @callback
    def ustaw_okres(self, rodzaj: str | None = None, dzien: date | None = None, koniec: date | None = None) -> None:
        """Zmiana okresu: przeliczenie z magazynu, bez API i bez ruszania timera odświeżania."""
        if rodzaj is not None:
            self.rodzaj = rodzaj
        if dzien is not None:
            self.dzien = dzien
        if koniec is not None:
            self.koniec = koniec
        self.data = self.przelicz()
        self.async_update_listeners()

    async def _async_update_data(self) -> Wynik | None:
        teraz = dt_util.utcnow()
        self.update_interval = ODSWIEZANIE  # przed _pobierz: wyjątek też nie zostawia krótkiego interwału po 429
        if self._nie_przed is None or teraz >= self._nie_przed:
            await self._pobierz(teraz)
        if self._nie_przed is not None and teraz < self._nie_przed:
            # następna próba zaraz po Retry-After; +1 s, bo HA ucina ułamek sekundy przy planowaniu
            self.update_interval = self._nie_przed - teraz + timedelta(seconds=1)
        return self.przelicz()

    async def _pobierz(self, teraz: datetime) -> None:
        """Dociąga godziny do magazynu; błędy API poza autoryzacją zostawiają dane z magazynu."""
        if self._godziny:
            start = datetime.fromisoformat(max(self._godziny)) - NAKLADKA
        else:
            start = teraz.replace(hour=0, minute=0, second=0, microsecond=0) - BACKFILL
        try:
            # koniec okna = pełna godzina: z minutami API oddaje bieżącą, jeszcze niepełną godzinę
            nowe = await self._klient.pobierz(start, teraz.replace(minute=0, second=0, microsecond=0))
        except PstrykAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except PstrykEndpointError as err:
            _LOGGER.warning("Pstryk odrzuca zapytanie (%s); liczę z magazynu", err)
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                ISSUE_ENDPOINT,
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key=ISSUE_ENDPOINT,
            )
            return
        except PstrykRateLimitError as err:
            self._nie_przed = teraz + timedelta(seconds=max(err.retry_after, MIN_RETRY_AFTER))
            _LOGGER.warning("Pstryk: limit zapytań, następna próba po %s", self._nie_przed)
            return
        except PstrykError as err:  # sieć, 5xx i nieobsłużone statusy (408, 402…)
            if not self._godziny:
                raise UpdateFailed(f"Pstryk niedostępny, magazyn pusty: {err}") from err
            _LOGGER.warning("Pstryk niedostępny (%s); liczę z magazynu", err)
            return
        self._godziny |= do_magazynu(nowe)  # po kluczu UTC: korekty i duplikaty ze styku okien nadpisują
        self.odczyty = z_magazynu(self._godziny)
        self.dane_z = teraz
        await self._store.async_save({"godziny": self._godziny, "dane_z": teraz.isoformat()})
        ir.async_delete_issue(self.hass, DOMAIN, ISSUE_ENDPOINT)
