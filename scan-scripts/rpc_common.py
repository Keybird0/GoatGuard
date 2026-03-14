#!/usr/bin/env python3
"""
Shared helpers for HTTP/RPC collection and provider failover.
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class QueryError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        retryable: bool,
        kind: str,
        status_code: Optional[int] = None,
    ) -> None:
        super().__init__(message)
        self.retryable = retryable
        self.kind = kind
        self.status_code = status_code


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def unique(items: Iterable[str]) -> List[str]:
    seen = set()
    ordered: List[str] = []
    for item in items:
        value = str(item).strip()
        if value and value not in seen:
            ordered.append(value)
            seen.add(value)
    return ordered


def normalize_output(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="ignore")
    return str(value)


def classify_text_error(message: str) -> QueryError:
    text = message.lower()
    retryable_markers = [
        "timeout",
        "timed out",
        "temporarily unavailable",
        "connection reset",
        "connection refused",
        "name or service not known",
        "nodename nor servname provided",
        "tls",
        "ssl",
        "429",
        "500",
        "502",
        "503",
        "504",
        "overloaded",
        "rate limit",
        "rate-limit",
        "network is unreachable",
    ]
    if any(marker in text for marker in retryable_markers):
        return QueryError(message, retryable=True, kind="transport")
    non_retryable_markers = [
        "execution reverted",
        "call reverted",
        "revert",
        "method not found",
        "invalid params",
        "invalid argument",
        "could not decode output",
        "selector was not recognized",
        "not enough data to decode",
    ]
    if any(marker in text for marker in non_retryable_markers):
        return QueryError(message, retryable=False, kind="business")
    return QueryError(message, retryable=False, kind="unknown")


def request_json(
    url: str,
    *,
    method: str = "GET",
    json_payload: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 15,
) -> Any:
    request_headers = {"User-Agent": "codex-token-audit/1.0"}
    if headers:
        request_headers.update(headers)
    data = None
    if json_payload is not None:
        data = json.dumps(json_payload).encode("utf-8")
        request_headers.setdefault("Content-Type", "application/json")
    request = Request(url, data=data, headers=request_headers, method=method)
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="ignore")
            if not body.strip():
                raise QueryError("empty response body", retryable=True, kind="empty")
            try:
                return json.loads(body)
            except json.JSONDecodeError as exc:
                raise QueryError(
                    f"non-json response: {exc}",
                    retryable=True,
                    kind="non-json",
                ) from exc
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        retryable = exc.code in {408, 429, 500, 502, 503, 504}
        raise QueryError(
            f"http {exc.code}: {body or exc.reason}",
            retryable=retryable,
            kind="http",
            status_code=exc.code,
        ) from exc
    except URLError as exc:
        raise QueryError(str(exc.reason), retryable=True, kind="transport") from exc
    except TimeoutError as exc:
        raise QueryError(str(exc), retryable=True, kind="timeout") from exc


def json_rpc_request(rpc_url: str, method: str, params: Sequence[Any], timeout: int = 15) -> Any:
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": list(params),
    }
    response = request_json(rpc_url, method="POST", json_payload=payload, timeout=timeout)
    if not isinstance(response, dict):
        raise QueryError("invalid JSON-RPC envelope", retryable=True, kind="non-json")
    if "error" in response and response["error"]:
        error = response["error"]
        message = error.get("message") if isinstance(error, dict) else str(error)
        code = error.get("code") if isinstance(error, dict) else None
        lowered = str(message).lower()
        retryable = code in {-32005, -32016} or "rate" in lowered or "timeout" in lowered or "overloaded" in lowered
        raise QueryError(
            f"json-rpc error {code}: {message}",
            retryable=retryable,
            kind="json-rpc",
        )
    return response.get("result")


def run_subprocess(
    command: Sequence[str],
    *,
    timeout: int = 30,
    cwd: Optional[Path] = None,
    env: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    try:
        result = subprocess.run(
            list(command),
            cwd=str(cwd) if cwd else None,
            env=env,
            text=True,
            capture_output=True,
            timeout=timeout,
        )
        return {
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "timed_out": False,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "returncode": 124,
            "stdout": normalize_output(exc.stdout),
            "stderr": normalize_output(exc.stderr) + f"\n[timeout] command exceeded {timeout}s",
            "timed_out": True,
        }


def record_attempt(
    *,
    provider: str,
    operation: str,
    elapsed_ms: int,
    success: bool,
    error: Optional[QueryError] = None,
) -> Dict[str, Any]:
    attempt = {
        "provider": provider,
        "operation": operation,
        "elapsed_ms": elapsed_ms,
        "success": success,
    }
    if error:
        attempt.update(
            {
                "error_kind": error.kind,
                "retryable": error.retryable,
                "error_message": str(error),
            }
        )
        if error.status_code is not None:
            attempt["status_code"] = error.status_code
    return attempt


def attempt_provider_operation(
    providers: Sequence[str],
    operation: str,
    func: Callable[[str], Any],
    *,
    start_index: int = 0,
) -> Dict[str, Any]:
    if not providers:
        return {
            "success": False,
            "attempts": [],
            "error": QueryError("no providers configured", retryable=False, kind="config"),
        }

    order = list(range(start_index, len(providers))) + list(range(0, start_index))
    attempts: List[Dict[str, Any]] = []
    last_error: Optional[QueryError] = None
    for index in order:
        provider = providers[index]
        started = time.perf_counter()
        try:
            result = func(provider)
        except QueryError as exc:
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            attempts.append(record_attempt(provider=provider, operation=operation, elapsed_ms=elapsed_ms, success=False, error=exc))
            last_error = exc
            if exc.retryable:
                continue
            return {
                "success": False,
                "provider": provider,
                "provider_index": index,
                "attempts": attempts,
                "error": exc,
            }

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        attempts.append(record_attempt(provider=provider, operation=operation, elapsed_ms=elapsed_ms, success=True))
        return {
            "success": True,
            "provider": provider,
            "provider_index": index,
            "attempts": attempts,
            "result": result,
        }

    return {
        "success": False,
        "attempts": attempts,
        "error": last_error or QueryError("all providers failed", retryable=True, kind="transport"),
    }


def flatten_attempts(sections: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    flat: List[Dict[str, Any]] = []
    for attempts in sections.values():
        flat.extend(attempts)
    return flat
