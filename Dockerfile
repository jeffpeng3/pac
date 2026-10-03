FROM python:3.13-alpine
WORKDIR /app
COPY proxy.pac.template server.py ./
ENV PROXY_TYPE=PROXY \
    PROXY_ADDR=127.0.0.1:7890 \
    PORT=8080
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://127.0.0.1:8080/healthz || exit 1
CMD ["python", "/app/server.py"]
