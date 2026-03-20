"""
Streamlit shim.

This project runs charts via FastAPI + React. Streamlit is not used anymore.
Some legacy chart modules still reference `st` in optional description helpers.
We provide `st = None` to avoid runtime dependency / side effects.
"""

st = None

