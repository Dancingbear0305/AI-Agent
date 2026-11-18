FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HOST=127.0.0.1 PORT=8080 DATA_DIR=/data
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt && groupadd -g 10001 lab && useradd -u 10001 -g lab -M lab && mkdir /data && chown lab:lab /data
COPY --chown=lab:lab app.py database.py /app/
COPY --chown=lab:lab static /app/static
USER lab
CMD ["python", "app.py"]
