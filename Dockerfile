FROM python:3.12-slim
ENV TZ=Asia/Seoul PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv
COPY pyproject.toml ./
COPY app ./app
RUN pip install --no-cache-dir .
COPY scripts ./scripts
# --no-access-log: 접근 로그에 /c/<token> 경로를 남기지 않기 위해
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
