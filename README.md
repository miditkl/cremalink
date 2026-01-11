# ☕ Cremalink

**A high-performance Python library and local API server for monitoring and controlling IoT coffee machines.**

[![PyPI version](https://img.shields.io/pypi/v/cremalink.svg?style=for-the-badge&color=blue)](https://pypi.org/project/cremalink/)
[![Python Version](https://img.shields.io/pypi/pyversions/cremalink.svg?style=for-the-badge&color=FFE169&labelColor=3776AB)](https://pypi.org/project/cremalink/)
[![License](https://img.shields.io/github/license/miditkl/cremalink?style=for-the-badge&color=success)](LICENSE)
[![Downloads](https://img.shields.io/pypi/dm/cremalink.svg?style=for-the-badge&color=orange)](https://pypi.org/project/cremalink/)
[![Source Code](https://img.shields.io/badge/Source-GitHub-black?style=for-the-badge&logo=github)](https://github.com/miditkl/cremalink)

---

## ✨ Overview

Cremalink provides a unified interface to interact with smart coffee machines via **Local LAN control** or **Cloud API**. It allows for real-time state monitoring and precise command execution.

> [!TIP]
> For detailed guides, advanced configuration, and developer deep-dives, please visit our **[Project Wiki](https://github.com/miditkl/cremalink/wiki)**.

---

## 🚀 Installation

Install the package via `pip` (Cremalink requires **Python 3.13+**):

```bash
pip install cremalink

```

### Optional Dependencies

To include tools for development or testing:

```bash
pip install "cremalink[dev]"   # For notebooks and kernel support
pip install "cremalink[test]"  # For running pytest suites

```

---

## 🛠 Usage

### Integrated API Server

Cremalink includes a FastAPI-based server for headless environments:

```bash
# Start the server (default port 10800)
cremalink-server --ip 0.0.0.0 --port 10800
```
> More information: [Local Server Setup](https://github.com/miditkl/cremalink/wiki/3.-Local-Server-Setup)

### Python API (Local Control)

Connect to your machine directly via your local network for the lowest latency

> More information: [Local Device]()

---

## 🛠 Development

### Testing

Run the comprehensive test suite using `pytest`:

```bash
pytest tests/

```

### Contributing

Contributions are welcome! If you have a machine profile not yet supported, please check the [Wiki: 5. Adding Custom Devices](https://github.com/miditkl/cremalink/wiki/) on how to add new `.json` device definitions.

Currently supported devices:

- `De'Longhi PrimaDonna Soul (AY008ESP1)`
---

## 📄 License

Distributed under the **AGPL-3.0-or-later** License. See `LICENSE` for more information.

---

*Developed by [Midian Tekle Elfu](mailto:developer@midian.tekleelfu.de). Supported by the community.*
