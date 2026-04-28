$env:PYTHONPATH = "D:\arasbotan\src"
Set-Location "D:\arasbotan"
python -m uvicorn api.main:app --host 127.0.0.1 --port 8080
