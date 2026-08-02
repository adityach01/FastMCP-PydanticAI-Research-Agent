python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python -m student.run --topic "US semiconductor export controls (2024-2025) overview" --out artifacts
