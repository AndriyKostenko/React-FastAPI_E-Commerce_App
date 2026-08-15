"""Versioned, cross-service wire contracts.

Service-internal request, response, and persistence schemas deliberately live
with their owning microservice.  Only payloads that cross a process boundary
belong here.
"""
