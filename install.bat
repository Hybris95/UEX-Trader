@echo off
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
echo Installation complete.
pause
