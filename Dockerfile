FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HOST=0.0.0.0 PORT=8080 DATA_DIR=/data
WORKDIR /app
RUN groupadd -g 10001 lab && useradd -u 10001 -g lab -M lab && mkdir /data && chown lab:lab /data
COPY --chown=lab:lab app.py /app/app.py
COPY --chown=lab:lab static /app/static
USER lab
EXPOSE 8080
CMD ["python", "app.py"]
