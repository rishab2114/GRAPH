from gffs.fetch import fetch_release, release_url


def test_release_url_quotes_ampersand():
    assert release_url("ATT&CK-v12.1") == (
        "https://raw.githubusercontent.com/mitre/cti/ATT%26CK-v12.1/enterprise-attack/enterprise-attack.json")


def test_fetch_uses_cache(tmp_path, monkeypatch):
    (tmp_path / "ATT&CK-v12.1.json").write_text("{}")

    def no_network(*a, **k):
        raise AssertionError("network")

    monkeypatch.setattr("gffs.fetch.requests.get", no_network)
    assert fetch_release("ATT&CK-v12.1", tmp_path) == tmp_path / "ATT&CK-v12.1.json"
