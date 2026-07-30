FROM python:3.11-slim

# Print logs immediately to SmarterASP log stream
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Replace main.py with the actual entry point file for your bot (e.g., bot.py, run.py)
CMD ["python", "main.py"]
