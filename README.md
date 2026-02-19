[![Static Badge](https://img.shields.io/badge/HACS-Custom-41BDF5?style=for-the-badge&logo=homeassistantcommunitystore&logoColor=white)](https://hacs.xyz/)
[![GitHub Release](https://img.shields.io/github/v/release/micpub/homeassistant-wanas?style=for-the-badge)](https://github.com/micpub/homeassistant-wanas/releases)


# Home Assistant integration for Wanas heat recovery ventilators (HRV) with "Display V2" controller

## Main features

- Built-in **dedicated Lovelace card** – clear, intuitive, and compact visualization of the HRV's status along with control (screenshots below)
- Full real-time communication (data refresh every 5 seconds by default – configurable)
- Communication via WiFi / Ethernet gateway (Modbus TCP ↔ Modbus RTU)
  - Dedicated support for **Waveshare** gateways – just enter the MAC address and the integration will automatically discover the device on your local network (LAN) and connect to it.
  - Manual IP + port configuration available for gateways from other manufacturers
- Displays current HRV errors
- Configuration via graphical user interface (**Config Flow**) – no YAML editing required
- Full **HACS** support


## Dedicated Lovelace Card

Custom Lovelace card that presents the most important HRV information in a clear and compact way while allowing quick control.

It automatically shows only the functions that are enabled in the device's service menu – this keeps the interface clean and free of unneeded elements.

On the card you will find:

- **Errors** – current issues
- **Current status** – fan speeds, temperatures, active modes and modules
- **Settings** – quick switching of modes and functions


## Requirements

- Home Assistant
- WiFi / Ethernet gateway (Modbus TCP ↔ Modbus RTU) – e.g. Waveshare RS232/485 TO WIFI POE ETH (B)
- Wanas heat recovery ventilator (HRV) with **Display V2** controller
- The gateway device must be on the same local network (LAN) as Home Assistant


## Installation

### Recommended method – via HACS (easiest)

1. Install the **Wanas** integration
2. Restart Home Assistant
3. Go to `Settings → Devices & Services → Add Integration`
4. Search for and select **Wanas**, then follow the configuration steps


---


# Integracja Home Assistant dla rekuperatorów Wanas ze sterownikiem "Display V2"

## Główne funkcje

- Wbudowana **dedykowana karta Lovelace** – czytelna, intuicyjna i skondensowana wizualizacja stanu rekuperatora wraz ze sterowaniem (zdjęcia poniżej)
- Pełna komunikacja w czasie rzeczywistym (odświeżanie danych domyślnie co 5 sekund – konfigurowalne)
- Komunikacja odbywa się poprzez bramkę WiFi / Ethernet (Modbus TCP ↔ Modbus RTU)
  - Dedykowane wsparcie dla bramek **Waveshare** – wystarczy podać adres MAC, a integracja automatycznie wyszuka urządzenie w sieci LAN i nawiąże z nim połączenie
  - Możliwość ręcznej konfiguracji IP + portu dla bramek innych producentów
- Wyświetlanie aktualnych błędów rekuperatora
- Konfiguracja przez graficzny interfejs użytkownika **Config Flow** (bez edycji yaml)
- Pełne wsparcie dla **HACS**


## Dedykowana karta Lovelace

Autorska karta Lovelace pokazuje najważniejsze informacje o rekuperatorze w czytelny i zwarty sposób oraz umożliwia szybkie sterowanie.

Automatycznie wyświetla wyłącznie funkcje aktywne w menu serwisowym urządzenia – dzięki temu interfejs pozostaje przejrzysty i wolny od zbędnych elementów.

Na karcie znajdziesz:

- **Błędy** – aktualne komunikaty o problemach
- **Aktualny stan** – obroty wentylatorów, temperatury, aktywne tryby i moduły
- **Ustawienia** – szybka zmiana trybów i funkcji


## Wymagania

- Home Assistant
- Bramka WiFi/Ethernet (Modbus TCP ↔ Modbus RTU) - np. Waveshare RS232/485 TO WIFI POE ETH (B)
- Rekuperator Wanas ze sterownikiem **Display V2**
- Urządzenie z bramką musi być w tej samej sieci LAN co Home Assistant


## Instalacja

### Sposób zalecany – przez HACS (najprostszy)

1. Zainstaluj integrację **Wanas**
2. Zrestartuj Home Assistant
3. Przejdź do `Ustawienia → Urządzenia oraz usługi → Dodaj integrację`
4. Wybierz **Wanas** i skonfiguruj


---


# Screenshoots / Zrzuty ekranu

<div style="max-width: 800px; margin: 0 auto; text-align: center;">
  <img src="https://raw.githubusercontent.com/micpub/homeassistant-wanas/main/images/en_dark_mobile_app.jpg"   width="49%">
  <span style="display:inline-block; width:1%;"></span>
  <img src="https://raw.githubusercontent.com/micpub/homeassistant-wanas/main/images/pl_light_mobile_app.jpg" width="49%">
</div>
