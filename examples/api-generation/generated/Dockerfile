FROM python:3.11-slim
WORKDIR /srv/api
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
ENV HOST=0.0.0.0 PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "exec uvicorn app.main:app --host \"$HOST\" --port \"$PORT\""]
