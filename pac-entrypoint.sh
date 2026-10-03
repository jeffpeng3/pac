#!/bin/bash
# 單一容器：WARP (gost :1080) ＋ PAC server (:8080) ＋ WPAD DNS (:53) ＋ port 80 relay
# WARP 協定棧、dnsmasq、port relay 放背景，PAC server 跑在前景當 PID 1
set -e

# 上游 warp-docker 啟動流程：dbus、warp-svc、註冊、gost
/entrypoint.sh &

# ---- WPAD DNS (dnsmasq)：wpad / wpad.<domain> 指到 docker 主機 IP ----
# PROXY_ADDR 格式 host:port，取 host 部分；只有 IPv4 才啟動 DNS
HOST_IP="${PROXY_ADDR%%:*}"
if [[ "$HOST_IP" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  # 只綁非 lo 介面，避免跟 docker 內嵌 DNS (127.0.0.11) 搶 port
  # 不依賴 iproute2，直接讀 /proc/net/route 找 default gateway 介面
  IFACE="$(awk '$2 == "00000000" {print $1; exit}' /proc/net/route 2>/dev/null || true)"
  LISTEN_ARGS=""
  if [ -n "$IFACE" ]; then
    LISTEN_ARGS="--interface=$IFACE --bind-interfaces"
  fi
  # shellcheck disable=SC2086
  sudo /usr/sbin/dnsmasq \
    --port=53 \
    --no-hosts \
    --no-resolv \
    --server="${WPAD_UPSTREAM:-1.1.1.1}" \
    --server=1.0.0.1 \
    --address="/wpad/$HOST_IP" \
    --address="/wpad.${WPAD_DOMAIN:-lan}/$HOST_IP" \
    $LISTEN_ARGS &
else
  echo "[wpad] PROXY_ADDR host 不是 IPv4 ($PROXY_ADDR)，跳過 WPAD DNS"
fi

# ---- port 80 relay：WPAD 固定抓 http://wpad.<domain>/wpad.dat (port 80) ----
# 轉給本機 PAC server，瀏覽器開「自動偵測 proxy」就能找到
sudo /usr/bin/gost -L "tcp://:80/127.0.0.1:${PORT:-8080}" &

# PAC server 跑在前景當 PID 1
exec python3 /app/server.py
