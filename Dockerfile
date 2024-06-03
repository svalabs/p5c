FROM python:3.12-alpine
WORKDIR /app
ENV KUBECONFIG=/app/config
COPY requirements.txt .
RUN pip install -r requirements.txt --no-cache
COPY main.py main.py
ENTRYPOINT ["python", "main.py"]
