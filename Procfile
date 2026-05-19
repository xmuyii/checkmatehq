worker: python main.py
web: python main.py
scheduler: python sync_to_sheets.py --daemon
web: uvicorn api_web:app --host 0.0.0.0 --port 8000
map: python map_api.py --host 0.0.0.0 --port 8001
bot: python main.py