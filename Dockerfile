FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir fastapi==0.115.* uvicorn==0.32.*
WORKDIR /uygulama
COPY app/ app/
COPY onayli/ onayli/
ENV KURAN_DB=/veri/kuran.db PYTHONUNBUFFERED=1
VOLUME /veri
EXPOSE 8120
CMD ["python", "-m", "uvicorn", "app.app:app", "--host", "0.0.0.0", "--port", "8120", "--app-dir", "/uygulama"]
