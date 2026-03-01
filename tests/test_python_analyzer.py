import subprocess

import pytest

from tools.python_analyzer import MAX_OUTPUT_BYTES, python_analyzer


def _mock_proc(mocker, returncode=0, stdout="", stderr=""):
    mock = mocker.MagicMock()
    mock.returncode = returncode
    mock.stdout = stdout
    mock.stderr = stderr
    return mock


class TestPythonAnalyzerUnit:
    def test_success_returns_result(self, mocker):
        mocker.patch(
            "tools.python_analyzer.subprocess.run",
            return_value=_mock_proc(mocker, returncode=0, stdout="hello\n"),
        )

        result = python_analyzer.invoke({"code": "print('hello')"})

        assert result == {"result": "hello\n"}

    def test_nonzero_exit_returns_error(self, mocker):
        mocker.patch(
            "tools.python_analyzer.subprocess.run",
            return_value=_mock_proc(mocker, returncode=1, stderr="SyntaxError: invalid"),
        )

        result = python_analyzer.invoke({"code": "def bad("})

        assert "error" in result
        assert "SyntaxError" in result["error"]

    def test_stdout_truncated_when_too_large(self, mocker):
        big_output = "x" * (MAX_OUTPUT_BYTES + 100)
        mocker.patch(
            "tools.python_analyzer.subprocess.run",
            return_value=_mock_proc(mocker, returncode=0, stdout=big_output),
        )

        result = python_analyzer.invoke({"code": "print('x' * 99999)"})

        assert result["result"].endswith("... [output truncated]")
        assert len(result["result"]) <= MAX_OUTPUT_BYTES + len("\n... [output truncated]")

    def test_empty_stdout_returns_no_output_message(self, mocker):
        mocker.patch(
            "tools.python_analyzer.subprocess.run",
            return_value=_mock_proc(mocker, returncode=0, stdout=""),
        )

        result = python_analyzer.invoke({"code": "x = 1"})

        assert "no output" in result["result"]

    def test_timeout_returns_error(self, mocker):
        mocker.patch(
            "tools.python_analyzer.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="docker", timeout=15),
        )

        result = python_analyzer.invoke({"code": "import time; time.sleep(999)"})

        assert "error" in result
        assert "timed out" in result["error"]

    def test_docker_not_found_returns_error(self, mocker):
        mocker.patch(
            "tools.python_analyzer.subprocess.run",
            side_effect=FileNotFoundError("docker not found"),
        )

        result = python_analyzer.invoke({"code": "print(1)"})

        assert "error" in result
        assert "Docker" in result["error"]

    def test_invalid_json_data_returns_error(self, mocker):
        mock_run = mocker.patch("tools.python_analyzer.subprocess.run")

        result = python_analyzer.invoke({"code": "print(1)", "data": "{not valid json"})

        assert "error" in result
        assert "invalid input data" in result["error"]
        mock_run.assert_not_called()

    def test_data_not_dict_returns_error(self, mocker):
        mock_run = mocker.patch("tools.python_analyzer.subprocess.run")

        result = python_analyzer.invoke({"code": "print(1)", "data": "[1, 2, 3]"})

        assert "error" in result
        assert "expected a JSON object" in result["error"]
        mock_run.assert_not_called()

    def test_stderr_on_success_adds_warnings(self, mocker):
        mocker.patch(
            "tools.python_analyzer.subprocess.run",
            return_value=_mock_proc(
                mocker, returncode=0, stdout="result\n", stderr="DeprecationWarning"
            ),
        )

        result = python_analyzer.invoke({"code": "print('result')"})

        assert result["result"] == "result\n"
        assert "warnings" in result
        assert "DeprecationWarning" in result["warnings"]


@pytest.mark.integration
class TestPythonAnalyzerIntegration:
    def test_real_docker_run_hello(self):
        result = python_analyzer.invoke({"code": "print('hello')"})

        assert "error" not in result
        assert result["result"].strip() == "hello"

    def test_real_docker_run_syntax_error(self):
        result = python_analyzer.invoke({"code": "def bad("})

        assert "error" in result
