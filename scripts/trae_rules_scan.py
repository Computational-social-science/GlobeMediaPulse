import argparse
import ast
import os
import re
import sys
import tokenize
import warnings
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Iterable, Iterator, Sequence


_CJK_RE = re.compile(r"[\u4e00-\u9fff]")
_WIN_USER_PATH_RE = re.compile(r"[A-Za-z]:(?:\\|/)Users(?:\\|/)")
_UNIX_HOME_RE = re.compile("/" + "home" + "/")
_UNIX_USERS_RE = re.compile("/" + "Users" + "/")


@dataclass(frozen=True)
class Finding:
    rule: str
    path: Path
    line: int
    message: str

    def format(self) -> str:
        return f"{self.rule}: {self.path.as_posix()}:{self.line}: {self.message}"


def _has_cjk(text: str) -> bool:
    return bool(_CJK_RE.search(text))


def _is_excluded_path(path: Path, excluded_dirs: set[str]) -> bool:
    for part in path.parts:
        if part in excluded_dirs:
            return True
    return False


def iter_repo_files(root: Path, excluded_dirs: set[str], included_suffixes: set[str]) -> Iterator[Path]:
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in excluded_dirs]
        for name in filenames:
            p = Path(dirpath) / name
            if _is_excluded_path(p, excluded_dirs):
                continue
            if p.suffix.lower() in included_suffixes:
                yield p


def scan_absolute_user_paths(path: Path) -> list[Finding]:
    try:
        raw = path.read_bytes()
    except Exception as e:
        return [Finding(rule="RULE3", path=path, line=1, message=f"Unreadable file ({e})")]

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return []

    findings: list[Finding] = []
    for i, line in enumerate(text.splitlines(), start=1):
        if _WIN_USER_PATH_RE.search(line) or _UNIX_HOME_RE.search(line) or _UNIX_USERS_RE.search(line):
            findings.append(Finding(rule="RULE3", path=path, line=i, message="Hardcoded user absolute path detected"))
    return findings


def _docstring_node_line(node: ast.AST) -> int:
    body = getattr(node, "body", None)
    if not isinstance(body, list) or not body:
        return 1
    first = body[0]
    if isinstance(first, ast.Expr) and isinstance(getattr(first, "value", None), ast.Constant):
        if isinstance(first.value.value, str):
            return int(getattr(first, "lineno", 1))
    return int(getattr(node, "lineno", 1))


def scan_python_language_constraint(path: Path) -> list[Finding]:
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return []

    findings: list[Finding] = []

    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError as e:
        return [Finding(rule="RULE4.1", path=path, line=int(getattr(e, "lineno", 1) or 1), message="SyntaxError")]

    module_doc = ast.get_docstring(tree)
    if module_doc and _has_cjk(module_doc):
        findings.append(
            Finding(rule="RULE4.1", path=path, line=_docstring_node_line(tree), message="CJK characters in module docstring")
        )

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            doc = ast.get_docstring(node)
            if doc and _has_cjk(doc):
                findings.append(
                    Finding(
                        rule="RULE4.1",
                        path=path,
                        line=_docstring_node_line(node),
                        message=f"CJK characters in docstring ({type(node).__name__} {getattr(node, 'name', '')})",
                    )
                )

        if isinstance(node, ast.ClassDef):
            if _has_cjk(node.name):
                findings.append(
                    Finding(rule="RULE4.1", path=path, line=int(getattr(node, "lineno", 1)), message="CJK in class name")
                )
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if _has_cjk(node.name):
                findings.append(
                    Finding(rule="RULE4.1", path=path, line=int(getattr(node, "lineno", 1)), message="CJK in function name")
                )
            for arg in node.args.args + node.args.kwonlyargs:
                if _has_cjk(arg.arg):
                    findings.append(
                        Finding(
                            rule="RULE4.1", path=path, line=int(getattr(arg, "lineno", node.lineno)), message="CJK in argument name"
                        )
                    )
            if node.args.vararg and _has_cjk(node.args.vararg.arg):
                findings.append(
                    Finding(
                        rule="RULE4.1",
                        path=path,
                        line=int(getattr(node.args.vararg, "lineno", node.lineno)),
                        message="CJK in vararg name",
                    )
                )
            if node.args.kwarg and _has_cjk(node.args.kwarg.arg):
                findings.append(
                    Finding(
                        rule="RULE4.1",
                        path=path,
                        line=int(getattr(node.args.kwarg, "lineno", node.lineno)),
                        message="CJK in kwarg name",
                    )
                )
        elif isinstance(node, ast.Name):
            if _has_cjk(node.id):
                findings.append(Finding(rule="RULE4.1", path=path, line=int(getattr(node, "lineno", 1)), message="CJK in identifier"))
        elif isinstance(node, ast.Attribute):
            if _has_cjk(node.attr):
                findings.append(
                    Finding(rule="RULE4.1", path=path, line=int(getattr(node, "lineno", 1)), message="CJK in attribute name")
                )
        elif isinstance(node, ast.alias):
            if _has_cjk(node.name) or (node.asname and _has_cjk(node.asname)):
                findings.append(
                    Finding(rule="RULE4.1", path=path, line=int(getattr(node, "lineno", 1)), message="CJK in import alias")
                )

    try:
        for tok in tokenize.generate_tokens(StringIO(text).readline):
            if tok.type == tokenize.COMMENT and _has_cjk(tok.string):
                findings.append(
                    Finding(rule="RULE4.1", path=path, line=int(tok.start[0]), message="CJK characters in comment")
                )
    except tokenize.TokenError:
        pass

    return findings


def run_scan(
    root: Path, excluded_dirs: set[str], included_suffixes: set[str], python_suffixes: set[str]
) -> list[Finding]:
    findings: list[Finding] = []
    for path in iter_repo_files(root=root, excluded_dirs=excluded_dirs, included_suffixes=included_suffixes):
        findings.extend(scan_absolute_user_paths(path))
        if path.suffix.lower() in python_suffixes:
            findings.extend(scan_python_language_constraint(path))
    return findings


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="trae_rules_scan", description="Scan repository for P0 rule violations (Rule 3, Rule 4.1).")
    p.add_argument("--root", default=".", help="Repository root directory.")
    p.add_argument(
        "--exclude-dir",
        action="append",
        default=[],
        help="Directory name to exclude (repeatable).",
    )
    return p.parse_args(list(argv))


def main(argv: Sequence[str]) -> int:
    warnings.filterwarnings("ignore", category=SyntaxWarning)
    args = parse_args(argv)
    root = Path(args.root).resolve()

    excluded_dirs = {
        ".git",
        ".venv",
        "venv",
        "__pycache__",
        "node_modules",
        "dist",
        "build",
        ".svelte-kit",
        ".vs",
        ".cursor",
        ".trae",
        "planning-with-files",
    }
    excluded_dirs.update(set(args.exclude_dir))

    included_suffixes = {
        ".py",
        ".js",
        ".ts",
        ".tsx",
        ".svelte",
        ".json",
        ".yml",
        ".yaml",
        ".toml",
        ".cfg",
        ".ini",
        ".sh",
        ".ps1",
        ".bat",
    }
    python_suffixes = {".py"}

    findings = run_scan(root=root, excluded_dirs=excluded_dirs, included_suffixes=included_suffixes, python_suffixes=python_suffixes)
    findings.sort(key=lambda f: (str(f.path).lower(), f.line, f.rule))

    if findings:
        for f in findings:
            print(f.format())
        print(f"TOTAL_VIOLATIONS={len(findings)}")
        return 1

    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
