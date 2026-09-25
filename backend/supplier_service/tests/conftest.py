"""Shared pytest configuration for supplier_service tests."""
import os

# Tests never call the Bank of Canada: prices use the configured rate.
os.environ.setdefault("CJ_FX_SOURCE", "fixed")
