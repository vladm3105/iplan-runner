"""``iplan-hermes`` command handlers."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from ..audit.report import build_audit_report
from ..config import load_config
from ..engine import HermesEngine, _default_clock
from ..executor.base import IdSource
from ..intake.payload import ingest_task_payload
from ..ledger.events import to_execution_events
from ..ledger.index import list_runs, set_control, status, store_control
from ..ledger.persistence import ledger_path, load, save
from ..monitoring.slo import evaluate_slos
from ..receiver import Heartbeat, ReceiverDeps, build_receiver
from ..relay import store as relay_store
from ..relay.client import IplanicClient
from ..relay.worker import drain
from ..validation.payload_rules import validate_payload

_DEFAULT_STORE = ".iops/ledgers"


def _load(path: str) -> dict[str, Any]:
    data: Any = yaml.safe_load(Path(path).read_text())
    return data if isinstance(data, dict) else {}


def _emit(result: Any) -> None:
    print(json.dumps(result, indent=2, sort_keys=True))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="iplan-hermes")
    sub = parser.add_subparsers(dest="command", required=True)

    p_ledger = sub.add_parser("ledger", help="ledger operations")
    p_ledger.add_argument("action", choices=["validate"])
    p_ledger.add_argument("path")

    p_gate = sub.add_parser("gate", help="run a verification gate")
    p_gate.add_argument("action", choices=["run"])
    p_gate.add_argument("ledger")
    p_gate.add_argument("gate")

    p_audit = sub.add_parser("audit", help="build an audit report")
    p_audit.add_argument("action", choices=["report"])
    p_audit.add_argument("baseline")
    p_audit.add_argument("comparison")

    p_monitor = sub.add_parser("monitor", help="monitoring operations")
    p_monitor.add_argument("action", choices=["validate", "slo-check"])
    p_monitor.add_argument("manifest")
    p_monitor.add_argument("samples", nargs="?")

    p_intake = sub.add_parser("intake", help="ingest + validate an SDD IPLAN or an Iplanic task payload")
    p_intake.add_argument("iplan", nargs="?")
    p_intake.add_argument("--payload", help="ingest an Iplanic remote task payload instead")

    p_emit = sub.add_parser("emit-events", help="project a signed ledger into Iplanic execution-events")
    p_emit.add_argument("ledger")
    p_emit.add_argument("--payload", required=True)
    p_emit.add_argument("--key-env", default="IOPS_SIGNING_KEY")
    p_emit.add_argument("--key-id", default=None)

    p_handover = sub.add_parser("handover", help="build + validate a handover receipt")
    p_handover.add_argument("ledger")
    p_handover.add_argument("gate")

    p_run = sub.add_parser("run", help="execute an IPLAN end-to-end")
    p_run.add_argument("iplan")
    p_run.add_argument("--store", default=_DEFAULT_STORE)
    p_run.add_argument("--actions", help="action script (uses the scripted executor)")
    p_run.add_argument("--workspace", default=".")
    p_run.add_argument("--land", action="store_true", help="commit changes if green")
    p_run.add_argument("--branch", default="iops/run")

    p_status = sub.add_parser("status", help="list runs or show one run's status")
    p_status.add_argument("ledger_id", nargs="?")
    p_status.add_argument("--store", default=_DEFAULT_STORE)

    p_verify = sub.add_parser("verify", help="verify a ledger's signatures")
    p_verify.add_argument("ledger")
    p_verify.add_argument("--key", required=True)

    p_sync = sub.add_parser("sync", help="on-demand: drain the local ledger to iplanic (off unless enabled)")
    p_sync.add_argument("ledger_id")
    p_sync.add_argument("--store", default=_DEFAULT_STORE)
    p_sync.add_argument("--config", default=None, help="config file with the iplanic sync block")
    p_sync.add_argument("--payload", help="iplanic task payload to persist the run identity from (first sync)")
    p_sync.add_argument("--key-env", default="IOPS_SIGNING_KEY")
    p_sync.add_argument("--key-id", default=None)
    p_sync.add_argument("--dry-run", action="store_true", help="report pending events without sending")

    p_server = sub.add_parser("server", help="run the inbound A2A task receiver (off unless receiver.enabled)")
    p_server.add_argument("--config", default=None, help="config file with the receiver + iplanic blocks")
    p_server.add_argument("--store", default=_DEFAULT_STORE)

    for name in ("pause", "abort"):
        p = sub.add_parser(name, help=f"{name} a run")
        p.add_argument("ledger_id")
        p.add_argument("--store", default=_DEFAULT_STORE)

    p_resume = sub.add_parser("resume", help="resume a paused/crashed run")
    p_resume.add_argument("iplan")
    p_resume.add_argument("--store", default=_DEFAULT_STORE)

    p_resolve = sub.add_parser("resolve", help="resolve a blocker")
    p_resolve.add_argument("ledger_id")
    p_resolve.add_argument("blocker_id")
    p_resolve.add_argument("decision", choices=["approve", "reject", "override"])
    p_resolve.add_argument("--store", default=_DEFAULT_STORE)
    p_resolve.add_argument("--role", default="operator")

    p_chain = sub.add_parser("run-chain", help="execute a chain of IPLANs")
    p_chain.add_argument("chain_file")

    return parser


def _sync(args: argparse.Namespace) -> int:
    """On-demand drain of a stored ledger to iplanic. No-op unless sync is enabled."""
    cfg = load_config(args.config)
    if not cfg.iplanic_sync_enabled:
        _emit({"sync": "disabled", "ledger_id": args.ledger_id})
        return 0
    endpoint = cfg.iplanic_endpoint
    if not endpoint:
        _emit({"error": "iplanic.endpoint not configured"})
        return 1
    ledger = load(ledger_path(args.store, args.ledger_id))
    identity = (
        relay_store.save_identity(args.store, args.ledger_id, _load(args.payload))
        if args.payload
        else relay_store.load_identity(args.store, args.ledger_id)
    )
    if not identity or not identity.get("run_id"):
        _emit({"error": "no iplanic identity persisted; pass --payload on the first sync"})
        return 1
    key = os.environ.get(args.key_env, "").encode()
    key_id = args.key_id or identity.get("executor_id") or "default"
    if args.dry_run:
        events = to_execution_events(ledger, identity, key=key, key_id=key_id)
        settled = relay_store.load_settled(args.store, args.ledger_id)
        pending = [e["idempotency_key"] for e in events if e["idempotency_key"] not in settled]
        _emit({"sync": "dry-run", "pending": pending, "total": len(events)})
        return 0
    token_env = cfg.iplanic_token_env
    client = IplanicClient(endpoint, lambda: os.environ.get(token_env))
    report = drain(
        ledger,
        identity,
        client=client,
        store_dir=args.store,
        ledger_id=args.ledger_id,
        key=key,
        key_id=args.key_id,
        max_age_s=cfg.iplanic_max_age_s,
    )
    _emit(
        {
            "sync": "ok" if report.ok else "halted",
            "delivered": len(report.delivered),
            "dead_lettered": len(report.dead_lettered),
            "pending": len(report.pending),
            "halted": report.halted,
        }
    )
    return 0 if report.ok else 1


def _server(args: argparse.Namespace) -> int:
    """Run the inbound A2A task receiver. No-op unless `receiver.enabled`."""
    cfg = load_config(args.config)
    if not cfg.receiver_enabled:
        _emit({"receiver": "disabled"})
        return 0
    token = os.environ.get(cfg.receiver_auth_env, "")
    if not token:
        _emit({"error": f"{cfg.receiver_auth_env} is empty; the receiver requires a bearer"})
        return 1
    endpoint = cfg.iplanic_endpoint
    if not endpoint:
        _emit({"error": "iplanic.endpoint not configured (the receiver drains events back to it)"})
        return 1

    def _log(message: str) -> None:
        print(f"[receiver] {message}", file=sys.stderr)

    def _token() -> str | None:
        return os.environ.get(cfg.iplanic_token_env)

    deps = ReceiverDeps(
        engine=HermesEngine(),
        store_dir=args.store,
        workspace=cfg.receiver_workspace,
        client=IplanicClient(endpoint, _token),
        key=(cfg.signing_key or "").encode(),
        key_id=cfg.receiver_key_id,
        log=_log,
    )
    try:
        server = build_receiver(
            bind=cfg.receiver_bind,
            port=cfg.receiver_port,
            token=token,
            deps=deps,
            max_parallel=cfg.receiver_max_parallel,
        )
    except (OSError, ValueError) as exc:
        _emit({"error": f"receiver failed to start: {exc}"})
        return 1

    heartbeat = None
    if cfg.receiver_executor_id and cfg.receiver_org_id:
        heartbeat = Heartbeat(
            endpoint=endpoint,
            executor_id=cfg.receiver_executor_id,
            org_id=cfg.receiver_org_id,
            token_provider=_token,
            interval_s=cfg.receiver_heartbeat_s,
            log=_log,
        )
        heartbeat.start()
    _log(f"listening on {cfg.receiver_bind}:{cfg.receiver_port}" + (" (heartbeat on)" if heartbeat else ""))
    try:
        server.serve_forever()
    except KeyboardInterrupt:  # pragma: no cover - operator Ctrl-C
        pass
    finally:
        if heartbeat is not None:
            heartbeat.stop()
        server.shutdown()
        server.server_close()
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    engine = HermesEngine()

    if args.command == "ledger":
        result = engine.validate(_load(args.path))
        _emit(result)
        return 0 if result["status"] != "fail" else 1

    if args.command == "gate":
        result = engine.run_gate(_load(args.ledger), _load(args.gate))
        _emit(result)
        return 0 if result["status"] == "passed" else 1

    if args.command == "audit":
        report = build_audit_report(_load(args.baseline), _load(args.comparison))
        validation = engine.validate(report)
        _emit({"report": report, "validation": validation})
        return 0 if validation["status"] != "fail" else 1

    if args.command == "monitor":
        manifest = _load(args.manifest)
        if args.action == "validate":
            result = engine.validate(manifest)
            _emit(result)
            return 0 if result["status"] != "fail" else 1
        samples = _load(args.samples) if args.samples else {}
        _emit(evaluate_slos(manifest, samples))
        return 0

    if args.command == "intake":
        if args.payload:
            manifest = ingest_task_payload(args.payload)
            findings = validate_payload(_load(args.payload))
            _emit({"manifest": manifest, "findings": [f.rule_id for f in findings]})
            return 0 if not findings else 1
        if not args.iplan:
            _emit({"error": "intake requires an IPLAN path or --payload"})
            return 1
        manifest = engine.ingest_iplan(args.iplan)
        validation = engine.validate(manifest)
        _emit({"manifest": manifest, "validation": validation})
        return 0 if validation["status"] != "fail" else 1

    if args.command == "emit-events":
        payload = _load(args.payload)
        ledger = _load(args.ledger)
        key = os.environ.get(args.key_env, "")
        key_id = args.key_id or payload.get("executor_id") or "default"
        events = to_execution_events(ledger, payload, key=key.encode(), key_id=key_id)
        _emit({"events": events})
        return 0

    if args.command == "handover":
        ledger = _load(args.ledger)
        gate_result = engine.run_gate(ledger, _load(args.gate))
        receipt = engine.build_handover(ledger, gate_result)
        validation = engine.validate(receipt)
        _emit({"receipt": receipt, "validation": validation})
        return 0 if validation["status"] != "fail" else 1

    if args.command == "run":
        manifest = engine.ingest_iplan(args.iplan)
        validation = engine.validate(manifest)
        if validation["status"] == "fail":
            _emit({"validation": validation})
            return 1
        executor = (
            engine.scripted_executor(_load(args.actions), args.workspace) if args.actions else engine.default_executor()
        )
        run_result = engine.run(manifest, executor, clock=_default_clock, ids=IdSource())
        if (
            args.land
            and run_result.gate_result["status"] == "passed"
            and run_result.ledger["reconciliation"]["allowed"]
        ):
            run_result = engine.land(
                run_result.ledger,
                args.workspace,
                branch=args.branch,
                message=f"iops: land {run_result.ledger['ledger_control']['ledger_id']}",
            )
        saved = save(run_result.ledger, args.store)
        receipt = engine.build_handover(run_result.ledger, run_result.gate_result)
        _emit(
            {
                "ledger_id": run_result.ledger["ledger_control"]["ledger_id"],
                "gate": run_result.gate_result["status"],
                "handover": receipt["result"],
                "saved": str(saved),
            }
        )
        return 0 if receipt["result"]["status"] == "completed" else 1

    if args.command == "status":
        if args.ledger_id:
            _emit(status(args.ledger_id, args.store))
        else:
            _emit(list_runs(args.store))
        return 0

    if args.command == "verify":
        verified = engine.verify_ledger(_load(args.ledger), args.key)
        _emit({"verified": verified})
        return 0 if verified else 1

    if args.command == "sync":
        return _sync(args)

    if args.command == "server":
        return _server(args)

    if args.command in ("pause", "abort"):
        set_control(args.ledger_id, "paused" if args.command == "pause" else "aborted", args.store)
        _emit({"ledger_id": args.ledger_id, "run_state": "paused" if args.command == "pause" else "aborted"})
        return 0

    if args.command == "resume":
        manifest = engine.ingest_iplan(args.iplan)
        ledger_id = "LEDGER-" + str(manifest["intake_control"]["source_iplan"])
        ledger = load(ledger_path(args.store, ledger_id))
        set_control(ledger_id, "running", args.store)
        resumed = engine.resume(
            manifest,
            ledger,
            engine.default_executor(),
            clock=_default_clock,
            ids=IdSource(),
            control=store_control(ledger_id, args.store),
        )
        save(resumed.ledger, args.store)
        _emit(
            {
                "ledger_id": ledger_id,
                "run_state": resumed.ledger["ledger_control"]["run_state"],
                "gate": resumed.gate_result["status"],
            }
        )
        return 0 if resumed.gate_result["status"] == "passed" else 1

    if args.command == "resolve":
        ledger = load(ledger_path(args.store, args.ledger_id))
        engine.resolve_blocker(ledger, args.blocker_id, args.decision, {"id": "cli", "role": args.role})
        save(ledger, args.store)
        _emit({"ledger_id": args.ledger_id, "blocker_id": args.blocker_id, "decision": args.decision})
        return 0

    if args.command == "run-chain":
        spec = _load(args.chain_file)
        chain_result = engine.run_chain(
            spec["chain"],
            spec["iplans"],
            lambda _iplan_id: engine.default_executor(),
            clock=_default_clock,
            ids=IdSource(),
        )
        ledger = chain_result.chain_ledger
        _emit(
            {
                "chain_id": ledger["chain_control"]["chain_id"],
                "execution_order": ledger["execution_order"],
                "iplan_chain": {n["iplan_id"]: n["reconciled"] for n in ledger["iplan_chain"]},
                "chain_reconciliation": ledger["chain_reconciliation"],
            }
        )
        return 0 if ledger["chain_reconciliation"]["allowed"] else 1

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
