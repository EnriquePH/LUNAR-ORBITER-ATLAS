import json

import pytest

from orbiter.config import AppConfig, load_config


def _write(tmp_path, data):
    path = tmp_path / "config.json"
    path.write_text(json.dumps(data))
    return path


def test_missing_file_uses_defaults(tmp_path):
    config = load_config(tmp_path / "missing.json")

    assert config == AppConfig()
    assert config.url == "http://127.0.0.1:8050/"


def test_reads_host_port_and_language(tmp_path):
    config = load_config(_write(tmp_path, {"port": 8051, "language": "en"}))

    assert (config.host, config.port, config.language) == ("127.0.0.1", 8051, "en")


@pytest.mark.parametrize(
    ("data", "message"),
    [
        ({"port": "8050"}, "port"),
        ({"port": 70000}, "port"),
        ({"language": "fr"}, "language"),
        ({"host": ""}, "host"),
        ({"prot": 8050}, "Unknown keys"),
    ],
)
def test_rejects_invalid_values(tmp_path, data, message):
    with pytest.raises(ValueError, match=message):
        load_config(_write(tmp_path, data))


def test_repository_config_pins_port_8050():
    assert load_config() == AppConfig(port=8050)
