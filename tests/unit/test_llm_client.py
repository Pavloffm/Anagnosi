from unittest.mock import MagicMock, patch

import requests

from anagnosi.rag.llm_client import LocalTransformersLLM, OllamaLLMClient


class TestOllamaHealthCheck:
    def test_health_check_success(self):
        with patch("requests.get") as mock_get:
            mock_get.return_value.status_code = 200
            client = OllamaLLMClient("http://localhost:11434", "model", 10, 0.1, 4096)
            assert client._health_check() is True

    def test_health_check_connection_error(self):
        with patch("requests.get", side_effect=requests.ConnectionError):
            client = OllamaLLMClient("http://localhost:11434", "model", 10, 0.1, 4096)
            assert client._health_check() is False

    def test_health_check_timeout(self):
        with patch("requests.get", side_effect=requests.Timeout):
            client = OllamaLLMClient("http://localhost:11434", "model", 10, 0.1, 4096)
            assert client._health_check() is False


class TestOllamaGenerate:
    def test_generate_success(self):
        client = OllamaLLMClient("http://localhost:11434", "model", 10, 0.1, 4096)

        mock_response = MagicMock()
        mock_response.json.return_value = {"response": "Hello World"}
        mock_response.raise_for_status.return_value = None

        with patch("requests.post", return_value=mock_response):
            result = client.generate("test prompt")
            assert result == "Hello World"

    def test_generate_timeout_returns_error_message(self):
        client = OllamaLLMClient("http://localhost:11434", "model", 10, 0.1, 4096)

        with patch("requests.post", side_effect=requests.Timeout):
            result = client.generate("test prompt")
            assert "timeout" in result.lower()

    def test_generate_connection_error_returns_error_message(self):
        client = OllamaLLMClient("http://localhost:11434", "model", 10, 0.1, 4096)

        with patch("requests.post", side_effect=requests.ConnectionError):
            result = client.generate("test prompt")
            assert "connect" in result.lower()

    def test_generate_http_error_returns_status_code(self):
        client = OllamaLLMClient("http://localhost:11434", "model", 10, 0.1, 4096)

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Error"
        mock_response.raise_for_status.side_effect = requests.HTTPError()

        with patch("requests.post", return_value=mock_response):
            result = client.generate("test prompt")
            assert "500" in result or "HTTP" in result


class TestOllamaGenerateStream:
    def test_stream_yields_chunks(self):
        client = OllamaLLMClient("http://localhost:11434", "model", 10, 0.1, 4096)

        mock_response = MagicMock()
        mock_response.iter_lines.return_value = [
            b'{"response": "Hello ", "done": false}',
            b'{"response": "World", "done": true}',
        ]
        mock_response.raise_for_status.return_value = None

        with patch("requests.post", return_value=mock_response):
            chunks = list(client.generate_stream("test"))
            assert chunks == ["Hello ", "World"]

    def test_stream_handles_timeout(self):
        client = OllamaLLMClient("http://localhost:11434", "model", 10, 0.1, 4096)

        with patch("requests.post", side_effect=requests.Timeout):
            chunks = list(client.generate_stream("test"))
            assert any("timeout" in chunk.lower() for chunk in chunks)


class TestLocalTransformersLLM:
    @patch("anagnosi.rag.llm_client.AutoTokenizer")
    @patch("anagnosi.rag.llm_client.AutoModelForCausalLM")
    @patch("anagnosi.rag.llm_client.pipeline")
    def test_local_llm_initialization(self, mock_pipeline, mock_model, mock_tokenizer):
        client = LocalTransformersLLM(model_name="test-model", device="cpu")
        assert client.pipe is not None

    @patch("anagnosi.rag.llm_client.AutoTokenizer")
    @patch("anagnosi.rag.llm_client.AutoModelForCausalLM")
    @patch("anagnosi.rag.llm_client.pipeline")
    def test_local_llm_generate_success(self, mock_pipeline, mock_model, mock_tokenizer):
        mock_pipe = MagicMock()
        mock_pipe.return_value = [{"generated_text": "<|assistant|>Response"}]
        mock_pipeline.return_value = mock_pipe

        client = LocalTransformersLLM(model_name="test-model", device="cpu")
        result = client.generate("test prompt")
        assert "Response" in result
