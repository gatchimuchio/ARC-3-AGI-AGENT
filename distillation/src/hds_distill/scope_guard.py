"""Deterministic, behavior-based Scope Guard for PH-D00B.

The guard parses audited Python source but never imports or executes it. It
combines AST behavior, resolved import provenance, declared entrypoints,
project dependencies, and repository boundaries. Findings are stable records
and the canonical report is content-bound.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import sys
import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, cast

type JsonScalar = None | bool | int | float | str
type JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue]
type JsonObject = dict[str, JsonValue]

PHASE_ID: Final = "PH-D00B"
SCOPE_ID: Final = "ARC3_HDS_DISTILLATION_SCOPE_D00B_V1"
REPORT_SCHEMA_VERSION: Final = "hds-distillation-scope-audit-v1"
REPORT_ID: Final = "HDS-DISTILLATION-SCOPE-AUDIT-PH-D00B-V1"
REPORT_DIGEST_NAMESPACE: Final = "hds-distillation-scope-audit"
REPORT_DIGEST_EXCLUDED_FIELDS: Final = ("content_digest", "report_id")

PYTHON_LOCK: Final = "3.12.13"
DEV_TOOL_LOCK: Final = (
    "mypy==1.17.1",
    "pytest==8.4.1",
    "ruff==0.12.7",
)
EXPECTED_ENTRYPOINTS: Final = {
    "hds-distillation-scope-guard": "hds_distill.scope_guard:main"
}

TRUSTED_TEACHER_MARKER: Final = (
    "hds_distill.scope_contract.teacher_bound"
)
TRUSTED_INTERPRETER_MARKER: Final = (
    "hds_distill.scope_contract.offline_interpreter"
)
TRUSTED_MARKER_NAMES: Final = frozenset(
    {"teacher_bound", "offline_interpreter"}
)

OFFICIAL_IMPORT_PREFIXES: Final = frozenset(
    {
        "arc_agi",
        "arc_agi_3",
        "arc_agi_toolkit",
        "kaggle",
    }
)
NETWORK_IMPORT_PREFIXES: Final = frozenset(
    {
        "aiohttp",
        "ftplib",
        "http.client",
        "httpx",
        "requests",
        "smtplib",
        "socket",
        "telnetlib",
        "urllib.request",
        "websockets",
        "xmlrpc.client",
    }
)
RUNTIME_IMPORT_PREFIXES: Final = frozenset(
    {
        "agents",
        "arc3_agi_agent",
        "bridge",
        "compiled_policy",
        "runtime",
        "s5_authority",
        "s5_compute",
        "s5_policy",
        "s5_runner",
        "s5_runtime",
        "teacher",
    }
)
DYNAMIC_CALLS: Final = frozenset(
    {
        "__import__",
        "builtins.__import__",
        "importlib.import_module",
        "importlib.util.module_from_spec",
        "runpy.run_module",
        "runpy.run_path",
    }
)
SOURCE_EXECUTION_CALLS: Final = frozenset(
    {
        "builtins.eval",
        "builtins.exec",
        "eval",
        "exec",
    }
)
SUBPROCESS_CALLS: Final = frozenset(
    {
        "subprocess.call",
        "subprocess.check_call",
        "subprocess.check_output",
        "subprocess.Popen",
        "subprocess.run",
    }
)
NETWORK_COMMAND_TOKENS: Final = frozenset(
    {"curl", "http://", "https://", "kaggle", "wget"}
)
SUBMISSION_WRITE_METHODS: Final = frozenset(
    {
        "open",
        "pathlib.Path.open",
        "pathlib.Path.write_bytes",
        "pathlib.Path.write_text",
        "to_csv",
        "to_json",
        "to_parquet",
        "write_bytes",
        "write_csv",
        "write_json",
        "write_parquet",
        "write_text",
    }
)
SUBMISSION_TOKENS: Final = frozenset(
    {
        "end_of_game",
        "episode_id",
        "game_id",
        "output",
        "row_id",
        "score",
        "submission",
    }
)
TASK_INPUT_TOKENS: Final = frozenset(
    {
        "challenge",
        "episode",
        "game",
        "grid",
        "level",
        "observation",
        "problem",
        "puzzle",
        "task",
    }
)
ANSWER_CALLABLE_TOKENS: Final = frozenset(
    {
        "act",
        "agent",
        "answer",
        "complete",
        "policy",
        "predict",
        "solve",
        "solver",
    }
)
TEACHER_EVIDENCE_TOKENS: Final = frozenset(
    {
        "answer",
        "expected",
        "ground",
        "label",
        "oracle",
        "solution",
        "target",
        "teacher",
        "trajectory",
        "truth",
    }
)
INTERPRETER_CALLABLE_TOKENS: Final = frozenset(
    {"interpret", "interpreter", "replay"}
)
IDENTITY_SELECTOR_NAMES: Final = frozenset(
    {
        "caseid",
        "episodeid",
        "gameid",
        "levelid",
        "taskid",
    }
)
ANSWER_LITERAL_TARGET_TOKENS: Final = frozenset(
    {
        "actionmap",
        "answer",
        "answermap",
        "fixedaction",
        "fixedactions",
        "replay",
        "replaymap",
        "solution",
        "solutionmap",
    }
)
ACTION_LITERAL_VALUES: Final = frozenset(
    {
        "ACTION1",
        "ACTION2",
        "ACTION3",
        "ACTION4",
        "ACTION5",
        "ACTION6",
        "DOWN",
        "LEFT",
        "RIGHT",
        "UP",
    }
)
CONFIG_SUFFIXES: Final = (
    "_CALLS",
    "_FIELDS",
    "_METHODS",
    "_NAMES",
    "_PREFIXES",
    "_ROOTS",
    "_SUFFIXES",
    "_TOKENS",
    "_VALUES",
)


class ScopeAuditError(RuntimeError):
    """A configuration-level failure that prevents a trustworthy audit."""


@dataclass(frozen=True, order=True, slots=True)
class Finding:
    """A deterministic scope violation."""

    code: str
    path: str
    line: int
    column: int
    symbol: str
    detail: str

    def as_json(self) -> JsonObject:
        return {
            "code": self.code,
            "column": self.column,
            "detail": self.detail,
            "line": self.line,
            "path": self.path,
            "symbol": self.symbol,
        }


@dataclass(frozen=True, slots=True)
class ModuleRecord:
    """Parsed source and statically resolved imports for one module."""

    path: str
    module: str
    package: str
    tree: ast.Module
    aliases: Mapping[str, str]
    imports: tuple[str, ...]
    symbols: frozenset[str]
    sha256: str
    size_bytes: int


@dataclass(frozen=True, slots=True)
class ProjectConfig:
    """Validated values read from the isolated pyproject."""

    name: str
    requires_python: str
    dependencies: tuple[str, ...]
    dev_dependencies: tuple[str, ...]
    entrypoints: Mapping[str, str]

    def as_json(self) -> JsonObject:
        return {
            "dependencies": list(self.dependencies),
            "dev_dependencies": list(self.dev_dependencies),
            "entrypoints": {
                key: self.entrypoints[key] for key in sorted(self.entrypoints)
            },
            "name": self.name,
            "requires_python": self.requires_python,
        }


def canonical_json(value: JsonValue) -> str:
    """Return canonical UTF-8 JSON text without a trailing newline."""

    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _content_digest(value: Mapping[str, JsonValue]) -> str:
    body = dict(value)
    for field in REPORT_DIGEST_EXCLUDED_FIELDS:
        body.pop(field, None)
    encoded = canonical_json(body).encode("utf-8")
    return REPORT_DIGEST_NAMESPACE + ":" + hashlib.sha256(encoded).hexdigest()


def _identifier_tokens(value: str) -> frozenset[str]:
    separated = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", value)
    return frozenset(
        token
        for token in re.split(r"[^a-z0-9]+", separated.casefold())
        if token
    )


def _compact_identifier(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def _matches_prefix(value: str, prefixes: frozenset[str]) -> bool:
    return any(
        value == prefix or value.startswith(prefix + ".")
        for prefix in prefixes
    )


def _relative_path(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError as exc:
        raise ScopeAuditError(
            f"D00B_PATH_OUTSIDE_REPOSITORY:{path}"
        ) from exc


def _file_manifest(path: Path, repository_root: Path) -> JsonObject:
    try:
        value = path.read_bytes()
    except OSError:
        return {
            "exists": False,
            "path": _relative_path(path, repository_root),
            "sha256": None,
            "size_bytes": 0,
        }
    return {
        "exists": True,
        "path": _relative_path(path, repository_root),
        "sha256": hashlib.sha256(value).hexdigest(),
        "size_bytes": len(value),
    }


def _module_name(path: Path, source_root: Path) -> tuple[str, str]:
    relative = path.relative_to(source_root)
    parts = list(relative.with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    module = ".".join(parts)
    if not module:
        raise ScopeAuditError(f"D00B_EMPTY_MODULE_NAME:{path}")
    package = module if path.name == "__init__.py" else module.rpartition(".")[0]
    return module, package


def _resolve_relative_import(
    *,
    package: str,
    level: int,
    imported_module: str | None,
) -> str:
    if level == 0:
        return imported_module or ""
    package_parts = package.split(".") if package else []
    remove_count = level - 1
    if remove_count > len(package_parts):
        return imported_module or ""
    prefix = package_parts[: len(package_parts) - remove_count]
    if imported_module:
        prefix.extend(imported_module.split("."))
    return ".".join(part for part in prefix if part)


class _ImportCollector(ast.NodeVisitor):
    def __init__(self, module: str, package: str, path: str) -> None:
        self.module = module
        self.package = package
        self.path = path
        self.aliases: dict[str, str] = {}
        self.imports: set[str] = set()
        self.findings: list[Finding] = []

    def visit_Import(self, node: ast.Import) -> None:
        for item in node.names:
            self.imports.add(item.name)
            bound_name = item.asname or item.name.split(".", 1)[0]
            self.aliases[bound_name] = item.name if item.asname else bound_name

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        base = _resolve_relative_import(
            package=self.package,
            level=node.level,
            imported_module=node.module,
        )
        if not base:
            self.findings.append(
                Finding(
                    code="D00B_IMPORT_RESOLUTION_FAILED",
                    path=self.path,
                    line=node.lineno,
                    column=node.col_offset,
                    symbol=self.module,
                    detail="relative import has no resolvable package",
                )
            )
        for item in node.names:
            if item.name == "*":
                self.findings.append(
                    Finding(
                        code="D00B_STAR_IMPORT_FORBIDDEN",
                        path=self.path,
                        line=node.lineno,
                        column=node.col_offset,
                        symbol=self.module,
                        detail=base or "<unresolved>",
                    )
                )
                continue
            imported = ".".join(part for part in (base, item.name) if part)
            self.imports.add(imported)
            self.aliases[item.asname or item.name] = imported


def _parse_module(
    path: Path,
    *,
    source_root: Path,
    repository_root: Path,
) -> tuple[ModuleRecord | None, list[Finding]]:
    relative = _relative_path(path, repository_root)
    module, package = _module_name(path, source_root)
    try:
        source_bytes = path.read_bytes()
        source = source_bytes.decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return None, [
            Finding(
                code="D00B_SOURCE_UNREADABLE",
                path=relative,
                line=0,
                column=0,
                symbol=module,
                detail=str(exc),
            )
        ]
    try:
        tree = ast.parse(source, filename=relative, type_comments=True)
    except (SyntaxError, ValueError) as exc:
        return None, [
            Finding(
                code="D00B_SOURCE_PARSE_FAILURE",
                path=relative,
                line=getattr(exc, "lineno", 0) or 0,
                column=getattr(exc, "offset", 0) or 0,
                symbol=module,
                detail=str(exc),
            )
        ]
    collector = _ImportCollector(module, package, relative)
    collector.visit(tree)
    symbols = frozenset(
        node.name
        for node in tree.body
        if isinstance(
            node,
            ast.AsyncFunctionDef | ast.ClassDef | ast.FunctionDef,
        )
    )
    return (
        ModuleRecord(
            path=relative,
            module=module,
            package=package,
            tree=tree,
            aliases=dict(collector.aliases),
            imports=tuple(sorted(collector.imports)),
            symbols=symbols,
            sha256=hashlib.sha256(source_bytes).hexdigest(),
            size_bytes=len(source_bytes),
        ),
        collector.findings,
    )


def _qualified_expression(
    node: ast.expr,
    aliases: Mapping[str, str],
) -> str:
    if isinstance(node, ast.Name):
        return aliases.get(node.id, node.id)
    if isinstance(node, ast.Attribute):
        parent = _qualified_expression(node.value, aliases)
        return ".".join(part for part in (parent, node.attr) if part)
    if isinstance(node, ast.Call):
        return _qualified_expression(node.func, aliases)
    return ""


def _string_literals(node: ast.AST) -> tuple[str, ...]:
    return tuple(
        item.value
        for item in ast.walk(node)
        if isinstance(item, ast.Constant) and isinstance(item.value, str)
    )


def _function_parameters(
    node: ast.AsyncFunctionDef | ast.FunctionDef,
) -> tuple[str, ...]:
    positional = (*node.args.posonlyargs, *node.args.args)
    keyword_only = tuple(node.args.kwonlyargs)
    names = [item.arg for item in (*positional, *keyword_only)]
    if node.args.vararg is not None:
        names.append(node.args.vararg.arg)
    if node.args.kwarg is not None:
        names.append(node.args.kwarg.arg)
    return tuple(names)


def _decorator_provenance(
    node: ast.AsyncFunctionDef | ast.FunctionDef,
    aliases: Mapping[str, str],
) -> tuple[frozenset[str], frozenset[str]]:
    resolved: set[str] = set()
    spellings: set[str] = set()
    for decorator in node.decorator_list:
        value = _qualified_expression(decorator, aliases)
        if value:
            resolved.add(value)
            spellings.add(value.rsplit(".", 1)[-1])
    return frozenset(resolved), frozenset(spellings)


def _names_in(node: ast.AST) -> frozenset[str]:
    names: set[str] = set()
    for item in ast.walk(node):
        if isinstance(item, ast.Name):
            names.add(_compact_identifier(item.id))
        elif isinstance(item, ast.Attribute):
            names.add(_compact_identifier(item.attr))
    return frozenset(names)


def _assignment_target_names(node: ast.AST) -> tuple[str, ...]:
    if isinstance(node, ast.Name):
        return (node.id,)
    if isinstance(node, ast.Attribute):
        return (node.attr,)
    if isinstance(node, ast.List | ast.Tuple):
        return tuple(
            name
            for item in node.elts
            for name in _assignment_target_names(item)
        )
    return ()


def _literal_sequence_values(node: ast.AST) -> tuple[str, ...]:
    if not isinstance(node, ast.List | ast.Set | ast.Tuple):
        return ()
    values: list[str] = []
    for item in node.elts:
        if isinstance(item, ast.Constant) and isinstance(item.value, str):
            values.append(item.value)
        else:
            return ()
    return tuple(values)


def _is_answer_literal(target: str, value: ast.AST) -> bool:
    upper_target = target.upper()
    if upper_target.endswith(CONFIG_SUFFIXES):
        return False
    compact = _compact_identifier(target)
    target_match = any(
        token in compact for token in ANSWER_LITERAL_TARGET_TOKENS
    )
    if not target_match:
        return False
    if isinstance(value, ast.Dict):
        return bool(value.keys)
    if isinstance(value, ast.List | ast.Tuple):
        if len(value.elts) < 2:
            return False
        if any(
            isinstance(item, ast.Dict | ast.List | ast.Tuple)
            for item in value.elts
        ):
            return True
        literal_values = _literal_sequence_values(value)
        return bool(literal_values) and all(
            item.upper() in ACTION_LITERAL_VALUES for item in literal_values
        )
    return False


def _has_main_guard(tree: ast.Module) -> bool:
    for node in tree.body:
        if not isinstance(node, ast.If):
            continue
        test = node.test
        if not isinstance(test, ast.Compare) or len(test.ops) != 1:
            continue
        values: tuple[ast.expr, ...] = (test.left, *test.comparators)
        has_name = any(
            isinstance(value, ast.Name) and value.id == "__name__"
            for value in values
        )
        has_main = any(
            isinstance(value, ast.Constant) and value.value == "__main__"
            for value in values
        )
        if has_name and has_main and isinstance(test.ops[0], ast.Eq):
            return True
    return False


def _is_submission_write(
    *,
    qualified_call: str,
    call: ast.Call,
    context_tokens: frozenset[str],
) -> bool:
    method = qualified_call.rsplit(".", 1)[-1]
    if (
        qualified_call not in SUBMISSION_WRITE_METHODS
        and method not in SUBMISSION_WRITE_METHODS
    ):
        return False
    call_tokens = set(context_tokens)
    for literal in _string_literals(call):
        call_tokens.update(_identifier_tokens(literal))
        lowered = literal.casefold()
        if "submission." in lowered or "submission/" in lowered:
            call_tokens.add("submission")
    if "submission" in call_tokens:
        return True
    return (
        {"row", "id", "output"} <= call_tokens
        or {"game", "id", "episode"} <= call_tokens
        or {"end", "of", "game", "score"} <= call_tokens
    )


class _BehaviorVisitor(ast.NodeVisitor):
    def __init__(self, record: ModuleRecord) -> None:
        self.record = record
        self.findings: list[Finding] = []
        self._function_depth = 0
        self._class_stack: list[str] = []
        self._callable_stack: list[str] = []
        self._context_stack: list[frozenset[str]] = []

    def _finding(
        self,
        code: str,
        node: ast.AST,
        symbol: str,
        detail: str,
    ) -> None:
        self.findings.append(
            Finding(
                code=code,
                path=self.record.path,
                line=getattr(node, "lineno", 0),
                column=getattr(node, "col_offset", 0),
                symbol=symbol,
                detail=detail,
            )
        )

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._class_stack.append(node.name)
        self.generic_visit(node)
        self._class_stack.pop()

    def _visit_function(
        self,
        node: ast.AsyncFunctionDef | ast.FunctionDef,
    ) -> None:
        is_public_boundary = self._function_depth == 0 and not node.name.startswith(
            "_"
        )
        qualified_symbol = ".".join((*self._class_stack, node.name))
        parameters = _function_parameters(node)
        parameter_tokens = frozenset(
            token
            for parameter in parameters
            for token in _identifier_tokens(parameter)
        )
        name_tokens = _identifier_tokens(node.name)
        resolved_markers, marker_spellings = _decorator_provenance(
            node,
            self.record.aliases,
        )
        task_like = bool(parameter_tokens & TASK_INPUT_TOKENS)
        answer_like = bool(name_tokens & ANSWER_CALLABLE_TOKENS)
        capability_like = task_like or answer_like
        teacher_evidence = bool(parameter_tokens & TEACHER_EVIDENCE_TOKENS)
        trusted_teacher = TRUSTED_TEACHER_MARKER in resolved_markers
        trusted_interpreter = TRUSTED_INTERPRETER_MARKER in resolved_markers
        interpreter_shape = bool(
            name_tokens & INTERPRETER_CALLABLE_TOKENS
        ) and not task_like

        if is_public_boundary and capability_like:
            marker_claimed = bool(marker_spellings & TRUSTED_MARKER_NAMES)
            marker_trusted = trusted_teacher or trusted_interpreter
            if marker_claimed and not marker_trusted:
                self._finding(
                    "D00B_UNTRUSTED_SCOPE_MARKER",
                    node,
                    qualified_symbol,
                    ",".join(sorted(marker_spellings & TRUSTED_MARKER_NAMES)),
                )
            allowed_teacher = trusted_teacher and teacher_evidence
            allowed_interpreter = trusted_interpreter and interpreter_shape
            if not (allowed_teacher or allowed_interpreter):
                self._finding(
                    "D00B_UNLABELED_TASK_PUBLIC_CALLABLE",
                    node,
                    qualified_symbol,
                    "public callable has task/answer capability without "
                    "trusted labeled-teacher or offline-interpreter closure",
                )

        function_tokens = set(name_tokens)
        for literal in _string_literals(node):
            function_tokens.update(_identifier_tokens(literal))
        self._function_depth += 1
        self._callable_stack.append(qualified_symbol)
        self._context_stack.append(frozenset(function_tokens))
        self.generic_visit(node)
        self._context_stack.pop()
        self._callable_stack.pop()
        self._function_depth -= 1

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node)

    def visit_Call(self, node: ast.Call) -> None:
        qualified = _qualified_expression(node.func, self.record.aliases)
        symbol = self._callable_stack[-1] if self._callable_stack else qualified
        if qualified in DYNAMIC_CALLS:
            self._finding(
                "D00B_DYNAMIC_IMPORT_FORBIDDEN",
                node,
                symbol,
                qualified,
            )
        if qualified in SOURCE_EXECUTION_CALLS:
            self._finding(
                "D00B_SOURCE_EXECUTION_FORBIDDEN",
                node,
                symbol,
                qualified,
            )
        if _matches_prefix(qualified, NETWORK_IMPORT_PREFIXES):
            self._finding(
                "D00B_NETWORK_CALL_FORBIDDEN",
                node,
                symbol,
                qualified,
            )
        if _matches_prefix(qualified, OFFICIAL_IMPORT_PREFIXES):
            self._finding(
                "D00B_OFFICIAL_API_CALL_FORBIDDEN",
                node,
                symbol,
                qualified,
            )
        if qualified in SUBPROCESS_CALLS:
            command_text = " ".join(_string_literals(node)).casefold()
            if any(token in command_text for token in NETWORK_COMMAND_TOKENS):
                self._finding(
                    "D00B_NETWORK_COMMAND_FORBIDDEN",
                    node,
                    symbol,
                    command_text,
                )
        context = (
            self._context_stack[-1] if self._context_stack else frozenset()
        )
        if _is_submission_write(
            qualified_call=qualified,
            call=node,
            context_tokens=context,
        ):
            self._finding(
                "D00B_SUBMISSION_OUTPUT_FORBIDDEN",
                node,
                symbol,
                qualified or "<unresolved-write-call>",
            )
        if qualified.endswith("listen_and_serve"):
            self._finding(
                "D00B_OFFICIAL_API_CALL_FORBIDDEN",
                node,
                symbol,
                qualified,
            )
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        qualified = _qualified_expression(node, self.record.aliases)
        if qualified.endswith("OperationMode.COMPETITION"):
            symbol = (
                self._callable_stack[-1]
                if self._callable_stack
                else qualified
            )
            self._finding(
                "D00B_COMPETITION_MODE_FORBIDDEN",
                node,
                symbol,
                qualified,
            )
        self.generic_visit(node)

    def visit_If(self, node: ast.If) -> None:
        identities = sorted(_names_in(node.test) & IDENTITY_SELECTOR_NAMES)
        if identities:
            symbol = (
                self._callable_stack[-1]
                if self._callable_stack
                else self.record.module
            )
            self._finding(
                "D00B_IDENTITY_SELECTOR_FORBIDDEN",
                node,
                symbol,
                ",".join(identities),
            )
        self.generic_visit(node)

    def visit_Match(self, node: ast.Match) -> None:
        identities = sorted(_names_in(node.subject) & IDENTITY_SELECTOR_NAMES)
        if identities:
            symbol = (
                self._callable_stack[-1]
                if self._callable_stack
                else self.record.module
            )
            self._finding(
                "D00B_IDENTITY_SELECTOR_FORBIDDEN",
                node,
                symbol,
                ",".join(identities),
            )
        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript) -> None:
        identities = sorted(_names_in(node.slice) & IDENTITY_SELECTOR_NAMES)
        if identities:
            symbol = (
                self._callable_stack[-1]
                if self._callable_stack
                else self.record.module
            )
            self._finding(
                "D00B_IDENTITY_SELECTOR_FORBIDDEN",
                node,
                symbol,
                ",".join(identities),
            )
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        for target_node in node.targets:
            for target in _assignment_target_names(target_node):
                if _is_answer_literal(target, node.value):
                    self._finding(
                        "D00B_ANSWER_LITERAL_OR_FIXED_ACTION_FORBIDDEN",
                        node,
                        target,
                        "literal answer map or fixed action sequence",
                    )
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if node.value is not None:
            for target in _assignment_target_names(node.target):
                if _is_answer_literal(target, node.value):
                    self._finding(
                        "D00B_ANSWER_LITERAL_OR_FIXED_ACTION_FORBIDDEN",
                        node,
                        target,
                        "literal answer map or fixed action sequence",
                    )
        self.generic_visit(node)


def _import_findings(record: ModuleRecord) -> list[Finding]:
    findings: list[Finding] = []
    for imported in record.imports:
        if _matches_prefix(imported, OFFICIAL_IMPORT_PREFIXES):
            code = "D00B_OFFICIAL_API_IMPORT_FORBIDDEN"
        elif _matches_prefix(imported, NETWORK_IMPORT_PREFIXES):
            code = "D00B_NETWORK_IMPORT_FORBIDDEN"
        elif _matches_prefix(imported, RUNTIME_IMPORT_PREFIXES):
            code = "D00B_RUNTIME_DEPENDENCY_FORBIDDEN"
        else:
            root = imported.split(".", 1)[0]
            if (
                root not in sys.stdlib_module_names
                and root != "hds_distill"
                and root != "__future__"
            ):
                code = "D00B_UNDECLARED_EXTERNAL_IMPORT"
            else:
                continue
        findings.append(
            Finding(
                code=code,
                path=record.path,
                line=0,
                column=0,
                symbol=record.module,
                detail=imported,
            )
        )
    return findings


def _read_project_config(
    project_root: Path,
    repository_root: Path,
) -> tuple[ProjectConfig, list[Finding]]:
    path = project_root / "pyproject.toml"
    relative = _relative_path(path, repository_root)
    findings: list[Finding] = []
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ScopeAuditError(f"D00B_PYPROJECT_UNREADABLE:{exc}") from exc
    project = cast(Mapping[str, object], raw.get("project", {}))
    optional = cast(
        Mapping[str, object],
        project.get("optional-dependencies", {}),
    )
    scripts = cast(Mapping[str, object], project.get("scripts", {}))
    tool = cast(Mapping[str, object], raw.get("tool", {}))
    mypy_config = cast(Mapping[str, object], tool.get("mypy", {}))
    ruff_config = cast(Mapping[str, object], tool.get("ruff", {}))
    pytest_config = cast(
        Mapping[str, object],
        tool.get("pytest", {}),
    )
    pytest_options = cast(
        Mapping[str, object],
        pytest_config.get("ini_options", {}),
    )

    name = str(project.get("name", ""))
    requires_python = str(project.get("requires-python", ""))
    dependencies = tuple(
        str(item)
        for item in cast(Sequence[object], project.get("dependencies", []))
    )
    dev_dependencies = tuple(
        sorted(
            str(item)
            for item in cast(Sequence[object], optional.get("dev", []))
        )
    )
    entrypoints = {
        str(key): str(value) for key, value in scripts.items()
    }

    def config_finding(code: str, detail: str) -> None:
        findings.append(
            Finding(
                code=code,
                path=relative,
                line=0,
                column=0,
                symbol="pyproject.toml",
                detail=detail,
            )
        )

    if name != "hds-distill":
        config_finding("D00B_PROJECT_IDENTITY_MISMATCH", name)
    if requires_python != "==3.12.13":
        config_finding(
            "D00B_PYTHON_LOCK_MISMATCH",
            f"expected===3.12.13:actual={requires_python}",
        )
    if dependencies:
        config_finding(
            "D00B_RUNTIME_DEPENDENCY_FORBIDDEN",
            ",".join(dependencies),
        )
    if dev_dependencies != tuple(sorted(DEV_TOOL_LOCK)):
        config_finding(
            "D00B_DEV_TOOL_LOCK_MISMATCH",
            ",".join(dev_dependencies),
        )
    if entrypoints != EXPECTED_ENTRYPOINTS:
        config_finding(
            "D00B_ENTRYPOINT_SET_MISMATCH",
            canonical_json(
                {
                    key: entrypoints[key] for key in sorted(entrypoints)
                }
            ),
        )
    if set(optional) != {"dev"}:
        config_finding(
            "D00B_OPTIONAL_DEPENDENCY_GROUP_MISMATCH",
            ",".join(sorted(str(key) for key in optional)),
        )
    if mypy_config.get("strict") is not True:
        config_finding("D00B_MYPY_STRICT_REQUIRED", "strict must be true")
    if str(mypy_config.get("python_version", "")) != "3.12":
        config_finding(
            "D00B_MYPY_PYTHON_VERSION_MISMATCH",
            str(mypy_config.get("python_version", "")),
        )
    if str(ruff_config.get("target-version", "")) != "py312":
        config_finding(
            "D00B_RUFF_TARGET_VERSION_MISMATCH",
            str(ruff_config.get("target-version", "")),
        )
    testpaths = tuple(
        str(item)
        for item in cast(
            Sequence[object],
            pytest_options.get("testpaths", []),
        )
    )
    if testpaths != ("tests",):
        config_finding(
            "D00B_PYTEST_BOUNDARY_MISMATCH",
            ",".join(testpaths),
        )
    return (
        ProjectConfig(
            name=name,
            requires_python=requires_python,
            dependencies=dependencies,
            dev_dependencies=dev_dependencies,
            entrypoints=entrypoints,
        ),
        findings,
    )


def _layout_findings(
    project_root: Path,
    repository_root: Path,
) -> list[Finding]:
    findings: list[Finding] = []

    def add(code: str, path: Path, detail: str) -> None:
        findings.append(
            Finding(
                code=code,
                path=_relative_path(path, repository_root),
                line=0,
                column=0,
                symbol=path.name,
                detail=detail,
            )
        )

    expected_directories = (
        project_root / "input",
        project_root / "schemas",
        project_root / "src" / "hds_distill",
        project_root / "tests" / "unit",
        project_root / "tests" / "integration",
        project_root / "artifacts" / "reports",
    )
    for path in expected_directories:
        if not path.is_dir():
            add("D00B_REQUIRED_DIRECTORY_MISSING", path, "required boundary")

    python_version_path = project_root / ".python-version"
    try:
        python_version = python_version_path.read_text(encoding="utf-8").strip()
    except OSError:
        python_version = ""
    if python_version != PYTHON_LOCK:
        add(
            "D00B_PYTHON_LOCK_MISMATCH",
            python_version_path,
            f"expected={PYTHON_LOCK}:actual={python_version}",
        )

    scope_lock = repository_root / "SCOPE_LOCK.md"
    try:
        scope_text = scope_lock.read_text(encoding="utf-8")
    except OSError:
        scope_text = ""
    required_scope_terms = (
        SCOPE_ID,
        "大平鉄兵",
        "DISTILLATION_SCOPE_GUARD_PASS",
        "filename",
    )
    for term in required_scope_terms:
        if term not in scope_text:
            add(
                "D00B_SCOPE_LOCK_INCOMPLETE",
                scope_lock,
                f"missing={term}",
            )

    for path in sorted(project_root.rglob("*")):
        if path.is_symlink():
            add(
                "D00B_SYMLINK_FORBIDDEN",
                path,
                "distillation boundary must not escape by symlink",
            )
    for path in sorted(project_root.rglob("*.py")):
        relative = path.relative_to(project_root)
        if relative.parts[0] not in {"src", "tests"}:
            add(
                "D00B_PYTHON_OUTSIDE_DECLARED_BOUNDARY",
                path,
                "Python must be under src or tests",
            )

    bridge_root = repository_root / "bridge"
    if not bridge_root.is_dir():
        add("D00B_BRIDGE_BOUNDARY_MISSING", bridge_root, "bridge must exist")
    else:
        bridge_files = sorted(
            path
            for path in bridge_root.rglob("*")
            if path.is_file() or path.is_symlink()
        )
        for path in bridge_files:
            if path.relative_to(bridge_root).as_posix() != ".gitkeep":
                add(
                    "D00B_BRIDGE_MUST_REMAIN_EMPTY",
                    path,
                    "only .gitkeep is permitted",
                )

    runtime_root = repository_root / "runtime"
    if not runtime_root.is_dir():
        add(
            "D00B_RUNTIME_REFERENCE_MISSING",
            runtime_root,
            "runtime reference must exist",
        )
    else:
        runtime_files = sorted(
            path
            for path in runtime_root.rglob("*")
            if path.is_file() or path.is_symlink()
        )
        for path in runtime_files:
            if path.relative_to(runtime_root).as_posix() != "REFERENCE_ONLY.md":
                add(
                    "D00B_RUNTIME_IMPLEMENTATION_FORBIDDEN",
                    path,
                    "runtime must remain documentation-only",
                )
    return findings


def _entrypoint_findings(
    config: ProjectConfig,
    modules: Sequence[ModuleRecord],
) -> list[Finding]:
    findings: list[Finding] = []
    module_index = {record.module: record for record in modules}
    declared_targets: set[tuple[str, str]] = set()
    for name, target in sorted(config.entrypoints.items()):
        module_name, separator, symbol = target.partition(":")
        if separator != ":" or not module_name or not symbol:
            findings.append(
                Finding(
                    code="D00B_ENTRYPOINT_TARGET_INVALID",
                    path="distillation/pyproject.toml",
                    line=0,
                    column=0,
                    symbol=name,
                    detail=target,
                )
            )
            continue
        declared_targets.add((module_name, symbol))
        record = module_index.get(module_name)
        if record is None or symbol not in record.symbols:
            findings.append(
                Finding(
                    code="D00B_ENTRYPOINT_TARGET_MISSING",
                    path="distillation/pyproject.toml",
                    line=0,
                    column=0,
                    symbol=name,
                    detail=target,
                )
            )
    for record in modules:
        if _has_main_guard(record.tree):
            if not any(
                module_name == record.module
                for module_name, _symbol in declared_targets
            ):
                findings.append(
                    Finding(
                        code="D00B_UNDECLARED_ENTRYPOINT",
                        path=record.path,
                        line=0,
                        column=0,
                        symbol=record.module,
                        detail="__main__ guard is not declared in pyproject",
                    )
                )
        if "main" in record.symbols and (
            record.module,
            "main",
        ) not in declared_targets:
            findings.append(
                Finding(
                    code="D00B_UNDECLARED_MAIN_CALLABLE",
                    path=record.path,
                    line=0,
                    column=0,
                    symbol=record.module + ".main",
                    detail="public main is not a declared entrypoint",
                )
            )
    return findings


def audit_project(
    project_root: Path,
    *,
    repository_root: Path | None = None,
) -> JsonObject:
    """Audit one isolated distillation tree without executing its source."""

    project_root = project_root.resolve()
    repository_root = (
        repository_root.resolve()
        if repository_root is not None
        else project_root.parent.resolve()
    )
    if project_root != repository_root / "distillation":
        raise ScopeAuditError(
            "D00B_PROJECT_ROOT_MUST_BE_REPOSITORY_DISTILLATION"
        )
    if not project_root.is_dir():
        raise ScopeAuditError(f"D00B_PROJECT_ROOT_MISSING:{project_root}")

    findings = _layout_findings(project_root, repository_root)
    config, config_findings = _read_project_config(
        project_root,
        repository_root,
    )
    findings.extend(config_findings)

    source_root = project_root / "src"
    modules: list[ModuleRecord] = []
    for path in sorted(source_root.rglob("*.py")):
        if path.is_symlink():
            continue
        record, parse_findings = _parse_module(
            path,
            source_root=source_root,
            repository_root=repository_root,
        )
        findings.extend(parse_findings)
        if record is None:
            continue
        modules.append(record)
        findings.extend(_import_findings(record))
        behavior = _BehaviorVisitor(record)
        behavior.visit(record.tree)
        findings.extend(behavior.findings)

    findings.extend(_entrypoint_findings(config, modules))

    actual_python = ".".join(
        str(item) for item in sys.version_info[:3]
    )
    if actual_python != PYTHON_LOCK:
        findings.append(
            Finding(
                code="D00B_AUDIT_INTERPRETER_MISMATCH",
                path="distillation/.python-version",
                line=0,
                column=0,
                symbol="python",
                detail=f"expected={PYTHON_LOCK}:actual={actual_python}",
            )
        )

    unique_findings = sorted(set(findings))
    import_graph: list[JsonValue] = [
        {
            "imports": list(record.imports),
            "module": record.module,
            "path": record.path,
        }
        for record in sorted(modules, key=lambda item: item.module)
    ]
    source_manifest: list[JsonValue] = [
        {
            "module": record.module,
            "path": record.path,
            "sha256": record.sha256,
            "size_bytes": record.size_bytes,
        }
        for record in sorted(modules, key=lambda item: item.module)
    ]
    boundary_paths = (
        repository_root / "SCOPE_LOCK.md",
        project_root / ".python-version",
        project_root / "README.md",
        project_root / "pyproject.toml",
        repository_root / "bridge" / ".gitkeep",
        repository_root / "runtime" / "REFERENCE_ONLY.md",
    )
    boundary_manifest: list[JsonValue] = [
        _file_manifest(path, repository_root) for path in boundary_paths
    ]
    entrypoints: JsonObject = {
        key: config.entrypoints[key] for key in sorted(config.entrypoints)
    }
    passed = not unique_findings
    report: JsonObject = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "report_id": REPORT_ID,
        "phase_id": PHASE_ID,
        "scope_id": SCOPE_ID,
        "project_root": "distillation",
        "analysis_mode": [
            "AST_WITHOUT_MODULE_EXECUTION",
            "RESOLVED_IMPORT_PROVENANCE",
            "DECLARED_ENTRYPOINTS",
            "PROJECT_DEPENDENCIES",
            "REPOSITORY_BOUNDARY",
        ],
        "audited_source_execution_count": 0,
        "python_lock": {
            "actual": actual_python,
            "expected": PYTHON_LOCK,
            "match": actual_python == PYTHON_LOCK,
        },
        "project_config": config.as_json(),
        "module_count": len(modules),
        "import_edge_count": sum(len(record.imports) for record in modules),
        "import_graph": import_graph,
        "source_manifest": source_manifest,
        "boundary_manifest": boundary_manifest,
        "entrypoints": entrypoints,
        "finding_count": len(unique_findings),
        "findings": [finding.as_json() for finding in unique_findings],
        "gates": {
            "DG-02": "PASS" if passed else "FAIL",
            "DG-09": "PASS" if passed else "FAIL",
            "DG-14": "PASS" if passed else "FAIL",
        },
        "scope_guard_pass": passed,
        "exit_claim": (
            "DISTILLATION_SCOPE_GUARD_PASS"
            if passed
            else "DISTILLATION_SCOPE_GUARD_FAIL"
        ),
        "claim_boundary": (
            "Repository and utilization-scope closure only; no corpus, "
            "causal, Rule-promotion, Bridge, AGI, locked-final, official, "
            "or submission claim."
        ),
        "owner_authority": "大平鉄兵",
        "digest_excluded_fields": list(REPORT_DIGEST_EXCLUDED_FIELDS),
        "content_digest": "",
    }
    report["content_digest"] = _content_digest(report)
    return report


def _report_bytes(report: JsonObject) -> bytes:
    return (canonical_json(report) + "\n").encode("utf-8")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Audit the PH-D00B distillation scope without execution."
    )
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--repository-root", required=True, type=Path)
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--write-report", type=Path)
    output.add_argument("--verify-report", type=Path)
    output.add_argument("--print-report", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the deterministic local gate."""

    arguments = _parser().parse_args(argv)
    try:
        report = audit_project(
            arguments.project_root,
            repository_root=arguments.repository_root,
        )
    except ScopeAuditError as exc:
        print(f"DISTILLATION_SCOPE_GUARD_ERROR:{exc}", file=sys.stderr)
        return 3

    encoded = _report_bytes(report)
    if arguments.write_report is not None:
        arguments.write_report.parent.mkdir(parents=True, exist_ok=True)
        arguments.write_report.write_bytes(encoded)
    elif arguments.verify_report is not None:
        try:
            expected = arguments.verify_report.read_bytes()
        except OSError as exc:
            print(
                f"DISTILLATION_SCOPE_GUARD_REPORT_UNREADABLE:{exc}",
                file=sys.stderr,
            )
            return 3
        if expected != encoded:
            print(
                "DISTILLATION_SCOPE_GUARD_REPORT_MISMATCH:"
                + str(arguments.verify_report),
                file=sys.stderr,
            )
            return 3
    elif arguments.print_report:
        sys.stdout.buffer.write(encoded)

    digest = str(report["content_digest"])
    if not bool(report["scope_guard_pass"]):
        print(
            "DISTILLATION_SCOPE_GUARD_FAIL:"
            + str(report["finding_count"])
            + ":"
            + digest,
            file=sys.stderr,
        )
        return 2
    print("DISTILLATION_SCOPE_GUARD_PASS:" + digest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
