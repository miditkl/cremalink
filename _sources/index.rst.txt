.. |logo| image:: ../../cremalink/resources/cremalink.png
   :height: 45px
   :valign: middle

|logo| cremalink
=================

**A high-performance Python library and local API server for monitoring and controlling IoT coffee machines.**

.. |PyPI version| image:: https://img.shields.io/pypi/v/cremalink.svg?style=for-the-badge&color=blue
   :target: https://pypi.org/project/cremalink/
.. |Python Version| image:: https://img.shields.io/pypi/pyversions/cremalink.svg?style=for-the-badge&color=FFE169&labelColor=3776AB
   :target: https://pypi.org/project/cremalink/
.. |License| image:: https://img.shields.io/github/license/miditkl/cremalink?style=for-the-badge&color=success
   :target: https://github.com/miditkl/cremalink/blob/main/LICENSE
.. |Downloads| image:: https://img.shields.io/pypi/dm/cremalink.svg?style=for-the-badge&color=orange
   :target: https://pypi.org/project/cremalink/
.. |Source Code| image:: https://img.shields.io/badge/Source-GitHub-black?style=for-the-badge&logo=github
   :target: https://github.com/miditkl/cremalink

|PyPI version| |Python Version| |License| |Downloads| |Source Code|

----

✨ Overview
----------

Cremalink provides a unified interface to interact with smart coffee machines via **Local LAN control** or **Cloud API**. It allows for real-time state monitoring and precise command execution.

.. tip::
   For detailed guides, advanced configuration, and developer deep-dives, please visit our `Project Wiki <https://github.com/miditkl/cremalink/wiki>`_.

.. note::
   This project was developed with a result-oriented approach, primarily optimized for the De'Longhi PrimaDonna Soul. While the architecture is designed to be extensible, some logic may currently be tightly coupled to this specific model and might not work seamlessly with others yet.
   The goal is to make the library fully generic. If you notice parts that are too specific to the PrimaDonna Soul or encounter issues with other machines, we highly encourage contributions! Refactoring and generalizations are very welcome to improve support for a wider range of devices.

----

🚀 Installation
--------------

Install the package via `pip` (Cremalink requires **Python 3.13+**):

.. code-block:: bash

   pip install cremalink

**Optional Dependencies**

To include tools for development or testing:

.. code-block:: bash

   pip install "cremalink[dev]"   # For notebooks and kernel support
   pip install "cremalink[test]"  # For running pytest suites

----

🛠 Usage
-------

**Integrated API Server**

Cremalink includes a FastAPI-based server for headless environments:

.. code-block:: bash

   # Start the server
   cremalink-server --ip 0.0.0.0 --port 10280 --settings_path "conf.json"

More information: `Local Server Setup <https://github.com/miditkl/cremalink/wiki/3.-Local-Server-Setup>`_

Python API (Local Control)
~~~~~~~~~~~~~~~~~~~~~~~~~~

Connect to your machine directly via your local network for the lowest latency.

More information: `Local Device Usage <https://github.com/miditkl/cremalink/wiki/4.-Local-Device-Usage>`_

----

🛠 Development
-------------

**Testing**

Run the comprehensive test suite using `pytest`:

.. code-block:: bash

   pytest tests/

**Contributing**

Contributions are welcome! If you have a machine profile not yet supported, please check the `Wiki: 5. Adding Custom Devices <https://github.com/miditkl/cremalink/wiki/5.-Adding-Custom-Devices>`_ on how to add new `.json` device definitions.

Currently supported devices:

* De'Longhi PrimaDonna Soul (AY008ESP1)

----

📄 License
---------

Distributed under the **AGPL-3.0-or-later** License. See `LICENSE <https://github.com/miditkl/cremalink/blob/main/LICENSE>`_ for more information.

----

Developed by `Midian Tekle Elfu <mailto:developer@midian.tekleelfu.de>`_. Supported by the community.


.. toctree::
   :maxdepth: 2
   :caption: Contents:
   :hidden:

   Home <self>
   modules


.. toctree::
   :maxdepth: 2
   :caption: API Reference
   :hidden:

   api/cremalink
