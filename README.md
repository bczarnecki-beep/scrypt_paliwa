# Ceny paliw dla landing page'a Cartrack

`pobierz_ceny.py` raz dziennie pobiera z AutoCentrum.pl średnie ceny Pb95 / Pb98 / ON
(Polska + 16 województw) i zapisuje je do `ceny.json`. Landing page w ActiveCampaign
czyta ten plik przez `ADRES_DANYCH` w BLOKU 00 – mapa, karty cen, kalkulator i FAQ
aktualizują się same.

| Plik | Rola |
|---|---|
| `pobierz_ceny.py` | skrypt pobierający (sam Python, bez bibliotek) |
| `ceny.json` | aktualne ceny – ten plik czyta strona |
| `historia.csv` | dzienne odczyty (do późniejszych wykresów / analiz) |
| `.github/workflows/aktualizuj-ceny.yml` | harmonogram: codziennie ok. 6:30 |

## Uruchomienie (jednorazowo, ok. 10 minut)

1. Załóż darmowe konto na github.com i utwórz **publiczne** repozytorium, `scrypt_paliwa`.
2. Wyślij do niego ten katalog:
   ```bash
   git init -b main
   git add .
   git commit -m "Start"
   git remote add origin https://github.com/bczarnecki-beep/scrypt_paliwa.git
   git push -u origin main
   ```
3. W repozytorium: **Settings → Pages → Source: Deploy from a branch → `main` / `(root)` → Save**.
4. **Settings → Actions → General → Workflow permissions → Read and write permissions → Save**.
5. Zakładka **Actions → Aktualizuj ceny paliw → Run workflow** – pierwszy test ręczny.
6. Sprawdź w przeglądarce: `https://bczarnecki-beep.github.io/scrypt_paliwa/ceny.json`
7. W ActiveCampaign, w BLOKU 00 wpisz ten adres:
   ```js
   ADRES_DANYCH: "https://bczarnecki-beep.github.io/scrypt_paliwa/ceny.json",
   ```

Od tej chwili GitHub sam uruchamia skrypt codziennie; komputer nie musi być włączony.

## Co warto wiedzieć

- **Rabat** zostaje w BLOKU 00 (`RABAT: 1.00`) – skrypt go nie nadpisuje.
- **Awaria źródła**: gdy AutoCentrum nie odpowiada albo zmieni układ strony, skrypt kończy się
  błędem i nie rusza `ceny.json` – strona pokazuje ostatnie dobre ceny, a GitHub wysyła
  e-mail o nieudanym uruchomieniu.
- **„—” na mapie** = AutoCentrum nie ma tego dnia notowań dla danego paliwa w województwie.
- **Skrypt tylko sprawdza, czy ceny się zmieniły.** Bez zmian → nic nie zapisuje (log: `BEZ ZMIAN`).
  Zmiana → nadpisuje `ceny.json`, dopisuje wiersze do `historia.csv`, a pole `data` dostaje
  dzień wykrycia zmiany. Lista różnic jest w logu uruchomienia (zakładka Actions).
- **Kontrola aktualności**: jeśli przez 7 dni z rzędu ceny w źródle się nie zmienią, uruchomienie
  kończy się błędem (e-mail z GitHuba) – sygnał, żeby ręcznie sprawdzić, czy AutoCentrum nadal
  aktualizuje dane. Próg: `DNI_BEZ_ZMIAN_ALARM` w skrypcie.
- **„Ceny na dzień …”** – każde miejsce w HTML z atrybutem `data-ct-data` pokazuje datę ostatniej
  zmiany cen (nie datę ostatniego sprawdzenia). Podpis pod tabelą/mapą:
  ```html
  <p class="ctlp-map-note">Ceny na dzień <span data-ct-data>21.09.2026</span>. Źródło: AutoCentrum.pl.</p>
  ```
- Ceny awaryjne wpisane na sztywno w HTML (SEO / brak JS) nie zmieniają się same – warto je
  odświeżyć ręcznie raz na jakiś czas.
- Sekcja „Cena ropy” i teksty prognoz nie są objęte automatem (brak ich w tym źródle).
- Dane pochodzą z AutoCentrum.pl – przed startem kampanii potwierdź z nimi / w ich regulaminie
  zgodę na automatyczne pobieranie i publikację; źródło jest podane w stopce strony.

## Test lokalny

```bash
python pobierz_ceny.py
```
