# 單一 image：WARP (gost :1080) ＋ PAC server (:8080) 同容器
FROM caomingjun/warp:latest

USER root

# server.py 只用 stdlib，最小安裝
RUN apt-get update && \
    apt-get install -y --no-install-recommends python3 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY server.py proxy.pac.template pac-entrypoint.sh pac-healthcheck.sh ./
RUN chmod +x /app/pac-entrypoint.sh /app/pac-healthcheck.sh && \
    chown -R warp:warp /app

USER warp

# 上游 WARP_* 與 GOST_ARGS 預設值沿用基底 image 的 ENV
# PAC 指向本機 WARP SOCKS，無需設定
ENV PORT=8080

EXPOSE 8080 1080

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD /app/pac-healthcheck.sh

ENTRYPOINT ["/app/pac-entrypoint.sh"]
