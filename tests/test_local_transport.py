import base64

from requests import Response

from cremalink.transports.local.transport import LocalTransport


class DummyResponse(Response):
    def __init__(self, status_code=200, json_data=None, text=""):
        super().__init__()
        self.status_code = status_code
        self._json_data = json_data
        self._text = text

        # self.text(text)

    def json(self, **kwargs):
        return self._json_data

    @property
    def text(self):
        return self._text


class DummyLocalTransport(LocalTransport):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs, auto_configure=False)
        self.calls = []
        self.configure_payloads = []

    def _post_server(self, path: str, body: dict, timeout: int = 10):
        self.calls.append(("POST", path))
        if path == "/configure":
            self.configure_payloads.append(body)
            return DummyResponse(200, {"status": "configured"})
        if path == "/command":
            return DummyResponse(200, {"status": "queued"})
        return DummyResponse(200, {})

    def _get_server(self, path: str, timeout: int = 10):
        self.calls.append(("GET", path))
        if path == "/health":
            return DummyResponse(200, text="ok")
        if path == "/get_properties":
            return DummyResponse(200, {"properties": {"prop": {"property": {"name": "prop", "value": "v"}}}, "received_at": 1.0})
        if path.startswith("/properties/"):
            return DummyResponse(200, {"value": "v"})
        if path == "/get_monitor":
            monitor_b64 = base64.b64encode(b"\x01\x02").decode("utf-8")
            return DummyResponse(200, {"monitor_b64": monitor_b64, "received_at": 1.0})
        if path == "/refresh_monitor":
            return DummyResponse(200, {})
        return DummyResponse(200, {})


def test_local_transport_flow():
    transport = DummyLocalTransport(
        dsn="dsn1",
        lan_key="lan",
        device_ip="1.2.3.4",
        server_host="localhost",
        server_port=1234,
        device_scheme="http",
        property_map={"monitor": "d302_monitor_machine"},
    )
    transport.configure()
    assert ("POST", "/configure") in transport.calls
    assert transport.configure_payloads[-1]["monitor_property_name"] == "d302_monitor_machine"

    result = transport.send_command("brew")
    assert result["status"] == "queued"

    props = transport.get_properties()
    assert props.get("prop")["property"]["value"] == "v"

    monitor = transport.get_monitor()
    assert monitor.raw_b64
    assert monitor.device_id == "dsn1"

    health = transport.health()
    assert health == "ok"
