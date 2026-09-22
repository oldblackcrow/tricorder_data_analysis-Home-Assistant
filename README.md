# Tricorder Data Analysis — Home Assistant (Screenshots are at the bottom of this file)

**Inspired by science fiction. Built for scientific discovery. Because “I wonder what that is?” should have a button.***

An open-source Home Assistant companion for collecting, visualizing, and exploring sensor data from network-connected instruments. It began with the TR-460 science tricorder, but you **don't need a tricorder or even to know what one is to use the ideas and tools here.**

The project is intended for tricorder builders, DIY instrument makers, STEM educators and students, makerspaces, and curious people experimenting with environmental or other scientific sensors. The LCARS-inspired interface gives it a science-fiction flavor; the sensor data is real data from the instruments you connect.

> If your device can send its measurements over a network, it may be able to use this platform. The current receiver expects a particular JSON telemetry format; other instruments may need a small adapter or field mapping. Compatibility with PiCorder, Next Gen, and other designs still needs testing.

## What it does

- Receives compatible sensor readings through a Home Assistant webhook and records them in local JSONL files.
- Organizes observations into selectable missions and archives.
- Shows interactive sensor cards, time-series graphs, and mission analysis.
- Includes example handling for radiation, atmospheric measurements, magnetic fields, orientation, color, UV, acoustic level, thermal readings, distance, and location when supplied.
- Keeps the Home Assistant integration separate from the instrument's hardware and firmware.

You can adapt the existing dashboard and data mappings for a tricorder, classroom experiment, environmental sensor package, or another custom instrument. **The current package is a starting point, not a universal plug-and-play driver for every networked sensor.**

## Who it's for
- **Astronomy & Astrophysics**
    The platform can also support astronomy and astrophysics projects, particularly experimental instrumentation and STEM education. Potential   applications include observatory environmental monitoring, telescope and instrument diagnostics, radio astronomy telemetry, and observation    archiving.
    With suitable sensors and adaptations, it could also support sky brightness measurements and astronomical spectroscopy.
    While not intended to replace specialized astronomical analysis software, it provides an accessible foundation for collecting, organizing,   and exploring data from custom-built astronomical instruments.
- **Tricorder builders:** Connect TR-460, PiCorder, Next Gen, or another designs by matching the supported telemetry format.
- **STEM classrooms and science clubs:** Build instruments, collect measurements, and compare experimental runs.
- **Makers and open-source hardware developers:** Give homemade sensor packages a Home Assistant interface and mission archive.
- **Citizen-science and environmental projects:** Organize readings from compatible field or stationary sensors.

## What's in this repository

```text
packages/       Home Assistant packages and sensor definitions
tricorder/      Python archive and analysis utilities
setup/          Configuration snippets, scripts, example upload receiver
dashboard/      Tricorder and analysis views plus individual card YAML
examples/       Fictional sample data for testing
docs/           Installation, security, and source-inventory notes
```

This is the **Home Assistant side only**. Instrument firmware, OTA images, private mission archives, secrets, and unrelated household configuration are not included. Third-party themes, custom cards, fonts, artwork, and franchise media are not bundled.

## Optional Science Analysis

An optional [saved-mission baseline and exploratory deviation view](docs/SCIENCE-ANALYSIS.md) compares Mission A against a selected reference mission without adding any instrument firmware requirements. This feature is not a calibrated alarm or safety monitor.

## Getting started
1. Read [Installation](docs/INSTALLATION.md) and [Security](docs/SECURITY.md) **before** copying anything into Home Assistant.
2. Back up your existing Home Assistant installation. The source setup used **Home Assistant 2026.9.3**; other versions have not been verified.
3. Install the separately distributed `custom:html-template-card`, `card-mod`, and `browser_mod` dependencies described in the installation guide.
4. Merge the packages, Python files, scripts, and receiver configuration according to the guide. **Do not replace your whole `configuration.yaml`, `automations.yaml`, or `scripts.yaml`.**
5. Set up a private webhook and a local file notifier. Configure your instrument—or an adapter—to send the expected JSON records.
6. Import the included dashboard views, then confirm that mission selection changes the corresponding sensor cards.

You can explore the expected record structure in [`examples/`](examples/). The physical tricorder sender is **not** part of this repository.

## Project status and scientific use
This repository was extracted from a working TR-460 Home Assistant installation and checked offline. **It has not yet been installed and verified from scratch on a clean Home Assistant system or tested with every proposed instrument.** Additional sensor types, hardware adapters, and installation feedback are welcome.

It may be useful for education, exploratory measurement, prototyping, and community-science projects. It is **not presented as a calibrated, validated, or safety-certified scientific measurement system**. The suitability of any result depends on the connected instrument, its calibration, the measurement method, and the needs of your project.

## Privacy and security
Never commit live webhook IDs or URLs, tokens, `secrets.yaml`, Home Assistant `.storage` files, full backups, personal mission archives, or records containing private locations. Use a fresh webhook ID in your own installation and keep the receiver on trusted network paths; see [Security](docs/SECURITY.md).

## License and attribution
Original project code is intended for release under the **GNU General Public License v3.0**. See the repository's `LICENSE` file for the exact terms. Only material the contributors have rights to license is covered; third-party Home Assistant components and Star Trek-related material retain their respective owners' terms and rights. This is an independent fan-inspired project, not affiliated with or endorsed by the Star Trek rights holders.

## Help shape it
If you're using a different tricorder, a student-built sensor package, or an experimental instrument, testing and issue reports are welcome. Share the sensor types and data fields you needed to adapt, **not** private webhook links or real personal location data.

Mission Data Page
<img width="1902" height="1076" alt="image" src="https://github.com/user-attachments/assets/c4ae2d9b-9006-4ae8-9795-8406c501189b" />
<img width="725" height="872" alt="image" src="https://github.com/user-attachments/assets/77bfcb89-743f-494d-8082-7a6ab8e54082" />
<img width="697" height="847" alt="image" src="https://github.com/user-attachments/assets/a329ac40-a76b-41ef-954c-2d47cab00631" />

Mission Analysis Page
<img width="1916" height="1078" alt="image" src="https://github.com/user-attachments/assets/781d2d8e-f9a9-424c-9207-04b45c2f73c3" />
<img width="710" height="597" alt="image" src="https://github.com/user-attachments/assets/fa46cb4a-e43a-428c-9a77-ff39b354ae59" />
<img width="720" height="597" alt="image" src="https://github.com/user-attachments/assets/25637518-e921-4889-abfd-e0eeaeabf23f" />


Science Page
<img width="562" height="1021" alt="image" src="https://github.com/user-attachments/assets/bb052c8c-e7a0-4760-ba36-3cc8aab7e17f" />

