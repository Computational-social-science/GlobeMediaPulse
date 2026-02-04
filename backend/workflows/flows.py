import os
import time
import uuid
import logging
import inspect
import traceback
import contextvars
from pathlib import Path
from datetime import datetime, timedelta, timezone
import functools
from collections import deque
from typing import Any, Dict, List, Optional, Callable, Deque, Tuple

from pydantic import BaseModel, Field, ValidationError

_logger = logging.getLogger(__name__)

_current_run_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("workflow_run_id", default=None)
_current_parent_node_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("workflow_parent_node_id", default=None)

_RUN_BUFFER: Deque[Dict[str, Any]] = deque(maxlen=200)
_NODE_BUFFER: Deque[Dict[str, Any]] = deque(maxlen=2000)
_LOG_BUFFER: Deque[Dict[str, Any]] = deque(maxlen=4000)


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex}"


def _normalize_status(value: str) -> str:
    v = str(value or "").strip().lower()
    if v in ("completed", "success", "succeeded", "ok"):
        return "Completed"
    if v in ("failed", "error", "exception"):
        return "Failed"
    if v in ("running", "in_progress"):
        return "Running"
    if v in ("cancelled", "canceled"):
        return "Cancelled"
    return "Pending"


def _validate_parameters(fn: Callable[..., Any], parameters: Dict[str, Any]) -> None:
    sig = inspect.signature(fn)
    sig.bind(**(parameters or {}))


def _record_log(level: str, message: str, *, node_id: str | None, run_id: str | None) -> None:
    entry = {
        "id": _new_id("log"),
        "timestamp": _now_iso(),
        "level": str(level).upper(),
        "message": str(message),
        "taskId": node_id,
        "flowRunId": run_id,
    }
    _LOG_BUFFER.append(entry)
    if entry["level"] == "ERROR":
        _logger.error("%s", entry["message"])
    elif entry["level"] == "WARN":
        _logger.warning("%s", entry["message"])
    else:
        _logger.info("%s", entry["message"])


def _run_with_retries(
    fn: Callable[..., Any],
    args: Tuple[Any, ...],
    kwargs: Dict[str, Any],
    *,
    retries: int,
    retry_delays_s: List[int],
    node_id: str,
    run_id: str | None,
) -> Any:
    attempts = 0
    last_err: BaseException | None = None
    while True:
        attempts += 1
        try:
            _record_log("INFO", f"{fn.__name__} attempt {attempts}", node_id=node_id, run_id=run_id)
            return fn(*args, **kwargs)
        except Exception as e:
            last_err = e
            if attempts > int(retries):
                raise
            delay = retry_delays_s[min(attempts - 1, max(0, len(retry_delays_s) - 1))] if retry_delays_s else 0
            if delay:
                time.sleep(int(delay))
            continue


def task(*dargs, **dkwargs):
    retries = int(dkwargs.get("retries") or 0)
    retry_delays = dkwargs.get("retry_delay_seconds")
    retry_delays_s = list(retry_delays) if isinstance(retry_delays, (list, tuple)) else ([] if retry_delays is None else [int(retry_delays)])

    def _decorator(fn: Callable[..., Any]):
        @functools.wraps(fn)
        def _wrapped(*args: Any, **kwargs: Any):
            run_id = _current_run_id.get()
            parent_id = _current_parent_node_id.get()
            node_id = _new_id("task")
            started_at = _now_iso()
            node_record = {
                "id": node_id,
                "name": getattr(fn, "__name__", "task"),
                "kind": "task",
                "status": "Running",
                "progress": 0.0,
                "startedAt": started_at,
                "finishedAt": None,
                "reason": None,
                "flowRunId": run_id,
                "parentId": parent_id,
                "subflowId": None,
                "args": args,
                "kwargs": kwargs,
            }
            _NODE_BUFFER.append(node_record)
            _record_log("INFO", f"task.start {node_record['name']}", node_id=node_id, run_id=run_id)
            token = _current_parent_node_id.set(node_id)
            try:
                result = _run_with_retries(fn, args, kwargs, retries=retries, retry_delays_s=retry_delays_s, node_id=node_id, run_id=run_id)
                node_record["status"] = "Completed"
                node_record["progress"] = 1.0
                return result
            except Exception as e:
                node_record["status"] = "Failed"
                node_record["progress"] = 0.0
                node_record["reason"] = str(e)
                _record_log("ERROR", f"task.error {node_record['name']}: {e}", node_id=node_id, run_id=run_id)
                _record_log("ERROR", traceback.format_exc(), node_id=node_id, run_id=run_id)
                raise
            finally:
                node_record["finishedAt"] = _now_iso()
                _current_parent_node_id.reset(token)

        _wrapped.validate_parameters = lambda parameters: _validate_parameters(fn, parameters)  # type: ignore[attr-defined]
        _wrapped.__workflow_kind__ = "task"  # type: ignore[attr-defined]
        _wrapped.__workflow_name__ = getattr(fn, "__name__", "task")  # type: ignore[attr-defined]
        return _wrapped

    if dargs and callable(dargs[0]) and len(dargs) == 1 and not dkwargs:
        return _decorator(dargs[0])
    return _decorator


def flow(*dargs, **dkwargs):
    flow_name = dkwargs.get("name")

    def _decorator(fn: Callable[..., Any]):
        resolved_name = str(flow_name or getattr(fn, "__name__", "flow"))

        @functools.wraps(fn)
        def _wrapped(*args: Any, **kwargs: Any):
            is_top = _current_run_id.get() is None
            run_id = _new_id("flow-run") if is_top else _current_run_id.get()
            parent_id = _current_parent_node_id.get()
            node_id = _new_id("flow")
            started_at = _now_iso()

            node_record = {
                "id": node_id,
                "name": resolved_name,
                "kind": "flow",
                "status": "Running",
                "progress": 0.0,
                "startedAt": started_at,
                "finishedAt": None,
                "reason": None,
                "flowRunId": run_id,
                "parentId": parent_id,
                "subflowId": None,
                "args": args,
                "kwargs": kwargs,
            }
            _NODE_BUFFER.append(node_record)
            _record_log("INFO", f"flow.start {resolved_name}", node_id=node_id, run_id=run_id)

            run_record: Dict[str, Any] | None = None
            run_token = None
            parent_token = None
            if is_top:
                run_record = {
                    "id": run_id,
                    "name": resolved_name,
                    "status": "Running",
                    "startedAt": started_at,
                    "finishedAt": None,
                    "progress": 0.0,
                }
                _RUN_BUFFER.append(run_record)
                run_token = _current_run_id.set(run_id)
                parent_token = _current_parent_node_id.set(node_id)
            else:
                parent_token = _current_parent_node_id.set(node_id)

            try:
                result = fn(*args, **kwargs)
                node_record["status"] = "Completed"
                node_record["progress"] = 1.0
                if run_record is not None:
                    run_record["status"] = "Completed"
                    run_record["progress"] = 1.0
                return result
            except Exception as e:
                node_record["status"] = "Failed"
                node_record["progress"] = 0.0
                node_record["reason"] = str(e)
                _record_log("ERROR", f"flow.error {resolved_name}: {e}", node_id=node_id, run_id=run_id)
                _record_log("ERROR", traceback.format_exc(), node_id=node_id, run_id=run_id)
                if run_record is not None:
                    run_record["status"] = "Failed"
                    run_record["progress"] = 0.0
                raise
            finally:
                node_record["finishedAt"] = _now_iso()
                if run_record is not None:
                    run_record["finishedAt"] = node_record["finishedAt"]
                if parent_token is not None:
                    _current_parent_node_id.reset(parent_token)
                if run_token is not None:
                    _current_run_id.reset(run_token)

        _wrapped.name = resolved_name  # type: ignore[attr-defined]
        _wrapped.validate_parameters = lambda parameters: _validate_parameters(fn, parameters)  # type: ignore[attr-defined]
        _wrapped.__workflow_kind__ = "flow"  # type: ignore[attr-defined]
        _wrapped.__workflow_name__ = resolved_name  # type: ignore[attr-defined]
        return _wrapped

    if dargs and callable(dargs[0]) and len(dargs) == 1 and not dkwargs:
        return _decorator(dargs[0])
    return _decorator

from backend.core.config import settings


def _retry_delays_s() -> List[int]:
    return [10, 20, 40]


class SeedQueueParams(BaseModel):
    tiers: List[str] = Field(default_factory=lambda: ["Tier-0", "Tier-1"])
    queue_key: str = Field(default_factory=lambda: settings.SEED_QUEUE_KEY)
    url_scheme: str = Field(default_factory=lambda: settings.SEED_URL_SCHEME)
    clear_existing: bool = True


class SeedQueueResult(BaseModel):
    queue_key: str
    pushed: int


class CrawlerTriggerParams(BaseModel):
    backend_api_url: str = Field(default="http://backend:8000")


class CrawlerTriggerResult(BaseModel):
    status: str
    message: str


class WaitForArticlesParams(BaseModel):
    min_new_articles: int = 10
    lookback_minutes: int = 30
    timeout_minutes: int = 15


class WaitForArticlesResult(BaseModel):
    found: int
    lookback_minutes: int


class CleanupParams(BaseModel):
    dry_run: bool = False


class CleanupResult(BaseModel):
    dry_run: bool


class TrainingParams(BaseModel):
    min_labeled_samples: int = 200
    test_size: float = 0.2
    random_state: int = 42


class TrainingResult(BaseModel):
    model_path: str
    label_values: List[str]
    train_rows: int
    test_rows: int


class ValidationParams(BaseModel):
    model_path: str


class ValidationResult(BaseModel):
    accuracy: float
    f1_macro: float


class ModelPathResult(BaseModel):
    model_path: str


@task(retries=3, retry_delay_seconds=_retry_delays_s(), timeout_seconds=1800, viz_return_value="Seed Queue")
def seed_start_urls(params: Dict[str, Any]) -> Dict[str, Any]:
    try:
        parsed = SeedQueueParams.model_validate(params)
    except ValidationError as e:
        raise ValueError(str(e))

    import psycopg2
    import redis

    redis_url = settings.REDIS_URL
    r = redis.from_url(redis_url)

    tiers = [t.strip() for t in parsed.tiers if t.strip()]
    domains: List[str] = []
    with psycopg2.connect(settings.DATABASE_URL) as conn:
        with conn.cursor() as cursor:
            if not tiers:
                cursor.execute("SELECT domain FROM media_sources")
            else:
                placeholders = ", ".join(["%s"] * len(tiers))
                cursor.execute(
                    f"SELECT domain FROM media_sources WHERE tier IN ({placeholders})",
                    tuple(tiers),
                )
            for row in cursor.fetchall():
                if row and row[0]:
                    domains.append(str(row[0]).strip().lower())

    key = parsed.queue_key
    if parsed.clear_existing:
        r.delete(key)

    pushed = 0
    for domain in domains:
        if not domain:
            continue
        url = f"{parsed.url_scheme}://{domain}"
        r.lpush(key, url)
        pushed += 1

    out = SeedQueueResult(queue_key=key, pushed=pushed)
    return out.model_dump()


@task(retries=3, retry_delay_seconds=_retry_delays_s(), timeout_seconds=1800, viz_return_value="Crawler Trigger")
def trigger_crawler(params: Dict[str, Any]) -> Dict[str, Any]:
    try:
        parsed = CrawlerTriggerParams.model_validate(params)
    except ValidationError as e:
        raise ValueError(str(e))

    import httpx

    url = parsed.backend_api_url.rstrip("/") + "/api/system/crawler/start"
    with httpx.Client(timeout=30) as client:
        resp = client.post(url)
        resp.raise_for_status()
        payload = resp.json()

    out = CrawlerTriggerResult(
        status=str(payload.get("status", "unknown")),
        message=str(payload.get("message", "")),
    )
    return out.model_dump()


def _count_recent_articles(conn, lookback_minutes: int) -> int:
    with conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM news_articles
            WHERE scraped_at >= NOW() - INTERVAL %s
            """,
            (f"{int(lookback_minutes)} minutes",),
        )
        row = cursor.fetchone()
        return int(row[0]) if row and row[0] is not None else 0


@task(retries=3, retry_delay_seconds=_retry_delays_s(), timeout_seconds=1800, viz_return_value="Wait Result")
def wait_for_articles(params: Dict[str, Any]) -> Dict[str, Any]:
    try:
        parsed = WaitForArticlesParams.model_validate(params)
    except ValidationError as e:
        raise ValueError(str(e))

    import psycopg2

    start = time.time()
    deadline = start + int(parsed.timeout_minutes) * 60
    min_new = int(parsed.min_new_articles)

    with psycopg2.connect(settings.DATABASE_URL) as conn:
        while True:
            found = _count_recent_articles(conn, parsed.lookback_minutes)
            if found >= min_new:
                out = WaitForArticlesResult(found=found, lookback_minutes=parsed.lookback_minutes)
                return out.model_dump()
            if time.time() >= deadline:
                raise TimeoutError(f"Only {found} articles found within timeout.")
            time.sleep(10)


@task(retries=3, retry_delay_seconds=_retry_delays_s(), timeout_seconds=1800, viz_return_value="Cleanup Result")
def run_cleanup(params: Dict[str, Any]) -> Dict[str, Any]:
    try:
        parsed = CleanupParams.model_validate(params)
    except ValidationError as e:
        raise ValueError(str(e))

    from backend.pipelines.cleanup_pipeline import cleanup_pipeline

    cleanup_pipeline.run(dry_run=bool(parsed.dry_run))
    out = CleanupResult(dry_run=bool(parsed.dry_run))
    return out.model_dump()


def _load_labeled_articles() -> Any:
    import pandas as pd
    import psycopg2

    with psycopg2.connect(settings.DATABASE_URL) as conn:
        df = pd.read_sql_query(
            """
            SELECT url, title, safety_label
            FROM news_articles
            WHERE safety_label IS NOT NULL
              AND title IS NOT NULL
              AND scraped_at IS NOT NULL
            """,
            conn,
        )
    df["safety_label"] = df["safety_label"].astype(str)
    df["title"] = df["title"].astype(str)
    df = df.dropna(subset=["safety_label", "title"])
    return df


@task(retries=3, retry_delay_seconds=_retry_delays_s(), timeout_seconds=1800, viz_return_value="Training Result")
def train_model(params: Dict[str, Any]) -> Dict[str, Any]:
    try:
        parsed = TrainingParams.model_validate(params)
    except ValidationError as e:
        raise ValueError(str(e))

    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import accuracy_score, f1_score
    from sklearn.model_selection import train_test_split

    df = _load_labeled_articles()
    if len(df) < int(parsed.min_labeled_samples):
        raise ValueError(f"Not enough labeled samples: {len(df)} < {parsed.min_labeled_samples}")

    X_train, X_test, y_train, y_test = train_test_split(
        df["title"].tolist(),
        df["safety_label"].tolist(),
        test_size=float(parsed.test_size),
        random_state=int(parsed.random_state),
        stratify=df["safety_label"].tolist(),
    )

    vectorizer = TfidfVectorizer(max_features=20000, ngram_range=(1, 2))
    X_train_vec = vectorizer.fit_transform(X_train)
    X_test_vec = vectorizer.transform(X_test)

    model = LogisticRegression(max_iter=200)
    model.fit(X_train_vec, y_train)

    y_pred = model.predict(X_test_vec)
    acc = float(accuracy_score(y_test, y_pred))
    f1 = float(f1_score(y_test, y_pred, average="macro"))

    ts = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_dir = Path(settings.BASE_DIR) / "data" / "models"
    out_dir.mkdir(parents=True, exist_ok=True)
    model_path = out_dir / f"safety_title_lr_{ts}.joblib"

    import joblib

    joblib.dump(
        {
            "vectorizer": vectorizer,
            "model": model,
            "metrics": {"accuracy": acc, "f1_macro": f1},
            "label_values": sorted(df["safety_label"].unique().tolist()),
        },
        model_path,
    )

    out = TrainingResult(
        model_path=str(model_path),
        label_values=sorted(df["safety_label"].unique().tolist()),
        train_rows=len(X_train),
        test_rows=len(X_test),
    )
    return out.model_dump()


@task(retries=3, retry_delay_seconds=_retry_delays_s(), timeout_seconds=1800, viz_return_value="Validation Result")
def validate_model(params: Dict[str, Any]) -> Dict[str, Any]:
    try:
        parsed = ValidationParams.model_validate(params)
    except ValidationError as e:
        raise ValueError(str(e))

    from sklearn.metrics import accuracy_score, f1_score
    import joblib

    bundle = joblib.load(parsed.model_path)
    vectorizer = bundle["vectorizer"]
    model = bundle["model"]

    df = _load_labeled_articles()
    if len(df) < 50:
        raise ValueError(f"Not enough labeled samples for validation: {len(df)}")

    X = vectorizer.transform(df["title"].tolist())
    y_true = df["safety_label"].tolist()
    y_pred = model.predict(X)

    out = ValidationResult(
        accuracy=float(accuracy_score(y_true, y_pred)),
        f1_macro=float(f1_score(y_true, y_pred, average="macro")),
    )
    return out.model_dump()


@task(retries=3, retry_delay_seconds=_retry_delays_s(), timeout_seconds=1800, viz_return_value="Report Result")
def generate_report(_: Dict[str, Any] | None = None) -> Dict[str, Any]:
    from backend.scripts.generate_weekly_report import generate_weekly_report

    generate_weekly_report()
    return {"status": "ok"}


@flow(name="data_acquisition_flow")
def data_acquisition_flow(
    seed_params: Optional[Dict[str, Any]] = None,
    crawler_params: Optional[Dict[str, Any]] = None,
    wait_params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    seeded = seed_start_urls(seed_params or {})
    triggered = trigger_crawler(crawler_params or {})
    waited = wait_for_articles(wait_params or {})
    return {"seed": seeded, "crawler": triggered, "wait": waited}


@flow(name="data_cleaning_flow")
def data_cleaning_flow(cleanup_params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    cleaned = run_cleanup(cleanup_params or {})
    return {"cleanup": cleaned}


@flow(name="model_training_flow")
def model_training_flow(training_params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    trained = train_model(training_params or {})
    return {"training": trained}


@flow(name="result_validation_flow")
def result_validation_flow(model_path: str) -> Dict[str, Any]:
    validated = validate_model({"model_path": model_path})
    return {"validation": validated}


@flow(name="report_generation_flow")
def report_generation_flow() -> Dict[str, Any]:
    out = generate_report()
    return {"report": out}


def _extract_model_path_value(payload: Any) -> Optional[str]:
    if isinstance(payload, dict):
        if "model_path" in payload:
            v = payload.get("model_path")
            if isinstance(v, str) and v.strip():
                return v.strip()
        for v in payload.values():
            found = _extract_model_path_value(v)
            if found:
                return found
    return None


@task(retries=3, retry_delay_seconds=_retry_delays_s(), timeout_seconds=1800, viz_return_value="Model Path")
def extract_model_path(payload: Any) -> str:
    model_path = _extract_model_path_value(payload)
    if not model_path:
        raise ValueError("model_path not found in payload")
    parsed = ModelPathResult(model_path=model_path)
    return parsed.model_path


@flow(name="core_business_flow")
def core_business_flow() -> Dict[str, Any]:
    acquisition = data_acquisition_flow()
    cleaning = data_cleaning_flow()
    training = model_training_flow()
    model_path = extract_model_path(training)
    validation = result_validation_flow(model_path=model_path)
    report = report_generation_flow()
    return {
        "acquisition": acquisition,
        "cleaning": cleaning,
        "training": training,
        "validation": validation,
        "report": report,
    }

def clear_workflow_buffers() -> None:
    _RUN_BUFFER.clear()
    _NODE_BUFFER.clear()
    _LOG_BUFFER.clear()


def _matches_search(value: str, query: str) -> bool:
    q = (query or "").strip().lower()
    if not q:
        return True
    return q in str(value or "").lower()


def _parse_time(value: str | None) -> float | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return float(dt.timestamp())
    except Exception:
        return None


def _node_to_ui(node: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": node.get("id"),
        "name": node.get("name"),
        "status": _normalize_status(node.get("status")),
        "progress": float(node.get("progress") or 0.0),
        "startedAt": node.get("startedAt"),
        "finishedAt": node.get("finishedAt"),
        "reason": node.get("reason"),
        "flowRunId": node.get("flowRunId"),
        "parentId": node.get("parentId"),
        "subflowId": node.get("subflowId"),
    }


def get_workflow_snapshot(
    *,
    from_iso: str | None = None,
    to_iso: str | None = None,
    statuses: List[str] | None = None,
    search: str | None = None,
) -> Dict[str, Any]:
    status_set = {str(s) for s in (statuses or []) if str(s).strip()}
    if not status_set:
        status_set = {"Pending", "Running", "Completed", "Failed", "Cancelled"}

    from_ts = _parse_time(from_iso)
    to_ts = _parse_time(to_iso)

    runs = list(_RUN_BUFFER)
    nodes = list(_NODE_BUFFER)
    logs = list(_LOG_BUFFER)

    flow_runs: List[Dict[str, Any]] = []
    for run in runs:
        run_id = str(run.get("id") or "")
        if not run_id:
            continue

        started_ts = _parse_time(run.get("startedAt"))
        if from_ts is not None and started_ts is not None and started_ts < from_ts:
            continue
        if to_ts is not None and started_ts is not None and started_ts > to_ts:
            continue

        run_name = str(run.get("name") or "")
        if not _matches_search(run_name, search or ""):
            continue

        run_status = _normalize_status(run.get("status") or "Running")
        if run_status not in status_set:
            continue

        run_nodes = [n for n in nodes if str(n.get("flowRunId") or "") == run_id]
        ui_nodes = [_node_to_ui(n) for n in run_nodes]
        edges: List[Dict[str, str]] = []
        for n in ui_nodes:
            parent_id = n.get("parentId")
            if parent_id:
                edges.append({"from": str(parent_id), "to": str(n.get("id"))})

        flow_runs.append(
            {
                "id": run_id,
                "name": run_name,
                "status": run_status,
                "startedAt": run.get("startedAt"),
                "finishedAt": run.get("finishedAt"),
                "progress": float(run.get("progress") or 0.0),
                "dag": {"nodes": ui_nodes, "edges": edges},
            }
        )

    ui_logs: List[Dict[str, Any]] = []
    for entry in logs:
        ts = _parse_time(entry.get("timestamp"))
        if from_ts is not None and ts is not None and ts < from_ts:
            continue
        if to_ts is not None and ts is not None and ts > to_ts:
            continue
        ui_logs.append(
            {
                "id": entry.get("id"),
                "timestamp": entry.get("timestamp"),
                "level": str(entry.get("level") or "INFO"),
                "message": entry.get("message"),
                "taskId": entry.get("taskId"),
                "flowRunId": entry.get("flowRunId"),
            }
        )

    return {
        "updatedAt": _now_iso(),
        "flows": flow_runs,
        "logs": ui_logs,
        "environment": {
            "orchestrator": "native",
            "pythonVersion": f"{os.sys.version_info.major}.{os.sys.version_info.minor}.{os.sys.version_info.micro}",
            "runtime": "in-process",
        },
    }


def list_workflows() -> List[str]:
    return [
        "data_acquisition_flow",
        "data_cleaning_flow",
        "model_training_flow",
        "result_validation_flow",
        "report_generation_flow",
        "core_business_flow",
    ]


def run_workflow(name: str, params: Optional[Dict[str, Any]] = None) -> Any:
    mapping: Dict[str, Callable[..., Any]] = {
        "data_acquisition_flow": data_acquisition_flow,
        "data_cleaning_flow": data_cleaning_flow,
        "model_training_flow": model_training_flow,
        "result_validation_flow": result_validation_flow,
        "report_generation_flow": report_generation_flow,
        "core_business_flow": core_business_flow,
    }
    fn = mapping.get(str(name or "").strip())
    if not fn:
        raise ValueError(f"Unknown workflow: {name}")
    if params is None:
        return fn()
    return fn(**params)
