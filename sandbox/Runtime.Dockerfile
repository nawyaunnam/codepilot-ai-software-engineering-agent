FROM python:3.12-slim
RUN pip install --no-cache-dir pytest && mkdir /source && chmod 755 /source
ENV PYTHONDONTWRITEBYTECODE=1 HOME=/tmp
USER 65534:65534
