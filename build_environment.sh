python -m venv .\venv
.\venv\Scripts\python -m pip config set global.index-url https://mirror.sjtu.edu.cn/pypi/web/simple
.\venv\Scripts\python -m pip install -r .\requirements.txt
pause