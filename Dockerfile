FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir -e .
COPY dashboard ./dashboard
COPY fixtures ./fixtures
RUN useradd --create-home app && chown -R app:app /app
USER app
EXPOSE 10000
CMD ["sh", "-c", "exec python -m uvicorn everymind_insight.server:create_app --factory --host 0.0.0.0 --port ${PORT:-10000} --workers 1 --proxy-headers --forwarded-allow-ips '*' --no-access-log"]
