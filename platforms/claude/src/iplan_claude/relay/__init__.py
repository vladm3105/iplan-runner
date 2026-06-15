"""iplanic transport (D-4b): drain the local signed ledger to `POST /v1/events`.

A per-engine relay (D-0011 strict isolation) over the existing durable ledger
(`ledger/persistence.py`), projection (`ledger/events.py:to_execution_events`),
and signer (`security/iplanic_signing.py`). Gated by a config sync toggle
(off by default), so standalone/offline runs are unaffected.
"""
