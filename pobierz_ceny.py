#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pobiera średnie ceny paliw (Pb95, Pb98, ON) z AutoCentrum.pl – Polska + 16 województw –
i zapisuje je do pliku ceny.json w formacie, który czyta landing page Cartrack
(USTAWIENIA.ADRES_DANYCH w BLOKU 00). Dopisuje też dzienny odczyt do historia.csv.

Uruchomienie:  python pobierz_ceny.py
Wymaga tylko Pythona 3.9+ (bez dodatkowych bibliotek).

Jeśli strona źródłowa nie odpowiada albo dane wyglądają podejrzanie, skrypt kończy się
błędem i NIE nadpisuje ceny.json – landing page dalej pokazuje ostatnie dobre ceny.
"""
import csv
import html
import json
import re
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

ADRES_ZRODLA = "https://www.autocentrum.pl/paliwa/ceny-paliw/"
KATALOG = Path(__file__).resolve().parent
PLIK_JSON = KATALOG / "ceny.json"
PLIK_HISTORII = KATALOG / "historia.csv"

# Kolejność jak na landing page'u: Pb95, Pb98, ON. Wartość = fragment adresu w AutoCentrum.
PALIWA = [("pb95", "pb"), ("pb98", "pb-premium"), ("on", "on")]

WOJEWODZTWA = [
    "dolnośląskie", "kujawsko-pomorskie", "lubelskie", "lubuskie", "łódzkie", "małopolskie",
    "mazowieckie", "opolskie", "podkarpackie", "podlaskie", "pomorskie", "śląskie",
    "świętokrzyskie", "warmińsko-mazurskie", "wielkopolskie", "zachodniopomorskie",
]

CENA_MIN, CENA_MAX = 3.0, 15.0      # zł/l – wszystko poza zakresem traktujemy jak błąd odczytu
MIN_WOJEWODZTW_Z_CENA = 10          # mniej = strona źródłowa się zmieniła albo ma awarię
DNI_BEZ_ZMIAN_ALARM = 7             # tyle dni bez żadnej zmiany cen = podejrzenie, że źródło stanęło


class BladDanych(Exception):
    pass


def pobierz_html(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; CartrackCenyPaliw/1.0; +https://www.cartrack.pl)",
        "Accept-Language": "pl-PL,pl;q=0.9",
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


def cena(tekst):
    """'7,86' -> 7.86; '-' / pusty / poza zakresem -> None."""
    m = re.search(r"\d{1,2}[.,]\d{1,2}", tekst or "")
    if not m:
        return None
    v = round(float(m.group(0).replace(",", ".")), 2)
    return v if CENA_MIN <= v <= CENA_MAX else None


def bez_tagow(fragment):
    return html.unescape(re.sub(r"<[^>]+>", " ", fragment)).strip()


def parsuj(strona):
    # --- średnie krajowe: kafelki <a href="/paliwa/ceny-paliw/pb/"> ... <div class="price"> 7,86
    polska = []
    for _, slug in PALIWA:
        m = re.search(
            r'href="/paliwa/ceny-paliw/' + re.escape(slug) + r'/"[^>]*>.*?<div class="price">(.*?)</div>',
            strona, re.S)
        polska.append(cena(bez_tagow(m.group(1))) if m else None)

    # --- tabela województw
    regiony = {}
    tabela = re.search(r'<table class="petrols-table.*?</table>', strona, re.S)
    if not tabela:
        raise BladDanych("Nie znaleziono tabeli województw (petrols-table).")
    for wiersz in re.findall(r"<tr>.*?</tr>", tabela.group(0), re.S):
        nazwa = re.search(r'class="row-link">(.*?)</a>', wiersz, re.S)
        if not nazwa:
            continue
        woj = bez_tagow(nazwa.group(1)).lower()
        if woj not in WOJEWODZTWA:
            continue
        ceny = []
        for _, slug in PALIWA:
            m = re.search(r'href="/paliwa/ceny-paliw/[^"/]+/' + re.escape(slug) + r'/"[^>]*>(.*?)</a>', wiersz, re.S)
            ceny.append(cena(bez_tagow(m.group(1))) if m else None)
        regiony[woj] = ceny
    return polska, regiony


def sprawdz(polska, regiony):
    if any(v is None for v in polska):
        raise BladDanych("Brak średniej krajowej dla któregoś paliwa: %r" % (polska,))
    brakujace = [w for w in WOJEWODZTWA if w not in regiony]
    if brakujace:
        raise BladDanych("Brak województw w tabeli: " + ", ".join(brakujace))
    z_cena = sum(1 for c in regiony.values() if any(v is not None for v in c))
    if z_cena < MIN_WOJEWODZTW_Z_CENA:
        raise BladDanych("Tylko %d województw ma jakąkolwiek cenę." % z_cena)


def dzisiaj():
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Europe/Warsaw")).date().isoformat()
    except Exception:                       # Windows bez pakietu tzdata
        return datetime.now().date().isoformat()


def wczytaj_poprzednie():
    """Ostatnio zapisane ceny albo None, gdy pliku jeszcze nie ma / jest uszkodzony."""
    try:
        return json.loads(PLIK_JSON.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def zmiany(stare, polska, regiony):
    """Lista opisów różnic między zapisanymi a świeżo pobranymi cenami (pusta = bez zmian)."""
    if not stare:
        return ["pierwszy zapis"]
    fmt = lambda v: "—" if v is None else "%.2f" % v
    wynik = []
    pary = [("Polska", stare.get("polska"), polska)]
    pary += [(w, (stare.get("regiony") or {}).get(w), regiony[w]) for w in WOJEWODZTWA]
    for nazwa, bylo, jest in pary:
        bylo = list(bylo or [])[:3] + [None] * (3 - len(bylo or []))
        for (paliwo, _), a, b in zip(PALIWA, bylo, jest):
            if a != b:
                wynik.append("%s %s: %s -> %s" % (nazwa, paliwo, fmt(a), fmt(b)))
    return wynik


def zapisz_json(data, polska, regiony):
    wynik = {
        "data": data,                       # dzień ostatniej ZMIANY cen – strona pokazuje go jako „ceny na dzień”
        "zrodlo": "AutoCentrum.pl",
        "polska": polska,
        "regiony": {w: regiony[w] for w in WOJEWODZTWA},
    }
    tmp = PLIK_JSON.with_suffix(".tmp")
    tmp.write_text(json.dumps(wynik, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(PLIK_JSON)


def zapisz_historie(data, polska, regiony):
    naglowek = ["data", "region", "pb95", "pb98", "on"]
    wiersze = []
    if PLIK_HISTORII.exists():
        with PLIK_HISTORII.open(encoding="utf-8", newline="") as f:
            wiersze = [w for w in csv.reader(f) if w and w[0] != "data" and w[0] != data]
    fmt = lambda v: "" if v is None else "%.2f" % v
    wiersze.append([data, "polska"] + [fmt(v) for v in polska])
    for w in WOJEWODZTWA:
        wiersze.append([data, w] + [fmt(v) for v in regiony[w]])
    with PLIK_HISTORII.open("w", encoding="utf-8", newline="") as f:
        out = csv.writer(f)
        out.writerow(naglowek)
        out.writerows(wiersze)


def main():
    try:
        polska, regiony = parsuj(pobierz_html(ADRES_ZRODLA))
        sprawdz(polska, regiony)
    except Exception as e:
        print("BŁĄD: %s\nceny.json pozostaje bez zmian." % e, file=sys.stderr)
        return 1
    stare = wczytaj_poprzednie()
    roznice = zmiany(stare, polska, regiony)
    if not roznice:
        print("BEZ ZMIAN – ceny takie same jak w odczycie z %s, nic nie zapisuję." % stare.get("data"))
        try:
            dni = (datetime.fromisoformat(dzisiaj()) - datetime.fromisoformat(stare["data"])).days
        except (KeyError, TypeError, ValueError):
            dni = 0
        if dni >= DNI_BEZ_ZMIAN_ALARM:
            print("UWAGA: ceny w źródle nie zmieniły się od %d dni – sprawdź ręcznie, czy AutoCentrum "
                  "nadal aktualizuje dane." % dni, file=sys.stderr)
            return 2            # nieudane uruchomienie = e-mail z GitHuba; ceny.json zostaje bez zmian
        return 0
    data = dzisiaj()
    zapisz_json(data, polska, regiony)
    zapisz_historie(data, polska, regiony)
    print("ZMIANA CEN – nowa data: %s (%d różnic)" % (data, len(roznice)))
    for r in roznice:
        print("  " + r)
    return 0


if __name__ == "__main__":
    sys.exit(main())
