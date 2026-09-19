"""
Application services: the ONLY backend surface the frontend may call.

Each function opens its own tenant-scoped unit of work, runs repository queries / analytics / ML, and
returns plain data (dicts, DataFrames, dataclasses). The frontend never sees a database session,
an ORM model or a SQL statement. `tests/test_architecture.py` enforces that boundary.
"""
