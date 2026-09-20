FROM python:3.12-slim
WORKDIR /srv
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/srv
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY pytest.ini ./pytest.ini
COPY mock_ehr_app.py ./mock_ehr_app.py
COPY start_combined.sh ./start_combined.sh
RUN chmod +x ./start_combined.sh
EXPOSE 8000
HEALTHCHECK --interval=20s --timeout=5s --retries=5 CMD python -c "import urllib.request,os; urllib.request.urlopen('http://localhost:'+(os.getenv('PORT','8000'))+'/health')"
CMD ["./start_combined.sh"]
