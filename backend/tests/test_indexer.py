from codepilot.indexer import parse_python
from codepilot.retrieval import tokens


def test_python_ast_chunks_have_exact_lines():
    source = "import os\n\ndef authenticate(user):\n    return bool(user)\n"
    chunks = parse_python("auth.py", source)
    assert chunks[0].symbol == "authenticate"
    assert chunks[0].start_line == 3
    assert chunks[0].end_line == 4
    assert chunks[0].dependencies == [("os", 1)]


def test_code_tokens_preserve_identifiers():
    assert "authentication_handler" in tokens("Authentication_Handler(request)")
