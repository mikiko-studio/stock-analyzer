@echo off
cd /d "%~dp0"
echo 株式統合分析ツールを起動しています...
pip install -r requirements.txt --quiet
python -m streamlit run app.py
pause
