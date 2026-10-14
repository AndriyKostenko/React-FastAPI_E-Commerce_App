"""Shared pytest configuration for supplier_service tests."""
import os

# Tests never call the Bank of Canada: prices use the configured rate.
os.environ.setdefault("CJ_FX_SOURCE", "fixed")
# Nor do they share the live CJ request budget in Redis or wait on it: the
# pacer is tested on its own (test_request_pacer.py) and clients that test it
# inject one.
os.environ.setdefault("CJ_DROPSHIPPING_RATE_LIMIT_ENABLED", "false")
