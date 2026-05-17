FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    DASHBOARD_BIND=0.0.0.0 \
    DASHBOARD_PORT=8095

WORKDIR /workspace

COPY src/dashboard_server.py /opt/collab-dashboard/dashboard_server.py

EXPOSE 8095

CMD ["python", "/opt/collab-dashboard/dashboard_server.py"]
