"""Provider contract tests without network calls."""
import json
from io import BytesIO
import pytest
from ontology_integration.document_provider import ChatCompletionsProvider

class FakeHTTP:
    def __init__(self, response): self.buf=BytesIO(response)
    def __enter__(self): return self
    def __exit__(self,*args): return False
    def read(self,size): return self.buf.read(size)

def test_provider_uses_configured_endpoint_and_parses_records(monkeypatch):
    captured=[]
    def fake(request,timeout):
        captured.append(request)
        assert timeout==2
        return FakeHTTP(json.dumps({"choices":[{"message":{"content":"[]"}}]}).encode())
    monkeypatch.setattr("ontology_integration.document_provider.urlopen",fake)
    provider=ChatCompletionsProvider(endpoint="https://example.org/v1/chat/completions",model="test",api_key="secret",timeout_seconds=2)
    assert provider({"chunk_id":"one","text":"robot action"})==[]
    assert captured[0].get_method()=="POST"
    assert b"robot action" in captured[0].data
    assert b"secret" not in captured[0].data

def test_provider_rejects_insecure_endpoint_and_bad_response(monkeypatch):
    with pytest.raises(ValueError,match="HTTPS"):
        ChatCompletionsProvider(endpoint="http://example.org",model="model",api_key="secret")
    monkeypatch.setattr("ontology_integration.document_provider.urlopen",
        lambda *a,**k:FakeHTTP(json.dumps({"choices":[{"message":{"content":"{\"not\":\"array\"}"}}]}).encode()))
    provider=ChatCompletionsProvider(endpoint="https://example.org/api",model="x",api_key="secret")
    with pytest.raises(ValueError,match="array|200"):
        provider({"text":"example"})
