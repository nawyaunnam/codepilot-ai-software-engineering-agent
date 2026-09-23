import ast
from dataclasses import dataclass
from pathlib import Path

from tree_sitter_language_pack import get_parser

EXTENSIONS = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".js": "javascript",
    ".jsx": "javascript",
    ".go": "go",
    ".java": "java",
}
IGNORED = {".git", "node_modules", "dist", "build", ".next", "vendor", ".venv", "target"}


@dataclass
class ParsedChunk:
    path: str
    language: str
    symbol: str
    kind: str
    start_line: int
    end_line: int
    content: str
    dependencies: list[tuple[str, int]]


def safe_files(root: Path):
    resolved = root.resolve()
    for p in resolved.rglob("*"):
        if p.is_symlink() or not p.is_file() or any(x in IGNORED for x in p.parts):
            continue
        if p.suffix in EXTENSIONS and p.stat().st_size < 1_000_000:
            yield p


def parse_python(path: str, text: str) -> list[ParsedChunk]:
    tree = ast.parse(text)
    lines = text.splitlines()
    imports = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            imports.extend((a.name, n.lineno) for a in n.names)
        elif isinstance(n, ast.ImportFrom):
            imports.append((n.module or "", n.lineno))
    out = []
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            end = getattr(n, "end_lineno", n.lineno)
            out.append(
                ParsedChunk(
                    path,
                    "python",
                    n.name,
                    type(n).__name__,
                    n.lineno,
                    end,
                    "\n".join(lines[n.lineno - 1 : end]),
                    imports,
                )
            )
    if not out:
        out.append(ParsedChunk(path, "python", "<module>", "module", 1, len(lines), text, imports))
    return out


def parse_treesitter(path: str, text: str, language: str) -> list[ParsedChunk]:
    parser = get_parser(language)
    data = text.encode()
    tree = parser.parse(data)
    lines = text.splitlines()
    deps = []
    out = []
    wanted = {
        "function_declaration",
        "method_definition",
        "class_declaration",
        "interface_declaration",
        "type_declaration",
        "function_definition",
        "method_declaration",
    }
    stack = [tree.root_node]
    while stack:
        n = stack.pop()
        stack.extend(n.children)
        if n.type in {"import_statement", "import_declaration"}:
            deps.append((data[n.start_byte : n.end_byte].decode()[:240], n.start_point[0] + 1))
        if n.type in wanted:
            name = n.child_by_field_name("name")
            symbol = data[name.start_byte : name.end_byte].decode() if name else n.type
            out.append(
                ParsedChunk(
                    path,
                    language,
                    symbol,
                    n.type,
                    n.start_point[0] + 1,
                    n.end_point[0] + 1,
                    data[n.start_byte : n.end_byte].decode(),
                    deps.copy(),
                )
            )
    for chunk in out:
        chunk.dependencies = deps.copy()
    if not out:
        out.append(ParsedChunk(path, language, "<module>", "module", 1, len(lines), text, deps))
    return out


def parse_file(root: Path, path: Path) -> list[ParsedChunk]:
    text = path.read_text(errors="replace")
    rel = str(path.relative_to(root))
    lang = EXTENSIONS[path.suffix]
    return parse_python(rel, text) if lang == "python" else parse_treesitter(rel, text, lang)
