FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends curl gnupg unixodbc-dev \
    && curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /usr/share/keyrings/msprod.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/msprod.gpg] https://packages.microsoft.com/debian/12/prod bookworm main" > /etc/apt/sources.list.d/mssql.list \
    && apt-get update && ACCEPT_EULA=Y apt-get install -y msodbcsql18 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY scripts ./scripts
COPY config ./config
RUN pip install --no-cache-dir poetry && poetry config virtualenvs.create false \
    && poetry install --extras ui --only main

ENV PYTHONPATH=/app/src
EXPOSE 8000
CMD ["streamlit", "run", "src/cryptoquantui/app.py", "--server.port=8000", "--server.address=0.0.0.0", "--server.headless=true"]
