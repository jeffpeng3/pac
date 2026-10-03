#!/bin/bash
# 三段都過才算健康：WARP 連線正常＋PAC 端點正常＋WPAD DNS 正常
set -e

# 上游檢查：socks trace 驗 warp=on/plus
bash /healthcheck/index.sh

# PAC server 檢查
curl -fsS "http://127.0.0.1:${PORT:-8080}/healthz" > /dev/null

# WPAD DNS 自檢：wpad.<domain> 必須解到 docker 主機 IP
HOST_IP="${PROXY_ADDR%%:*}"
if [[ "$HOST_IP" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  WPAD_HOST="wpad.${WPAD_DOMAIN:-lan}"
  RESOLVED="$(python3 - "$WPAD_HOST" <<'EOF'
import socket, struct, sys
name = sys.argv[1]
# 手工組一個 A 查詢封包
pkt = struct.pack('>HHHHHH', 0x1234, 0x0100, 1, 0, 0, 0)
for part in name.split('.'):
    pkt += bytes([len(part)]) + part.encode()
pkt += struct.pack('>HH', 1, 1)
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.settimeout(3)
s.sendto(pkt, ('127.0.0.1', 53))
data, _ = s.recvfrom(512)
# 跳過問題段，讀第一筆 answer 的 RDATA
i = 12 + len(pkt[12:-4]) + 4 + 1
n = len(data)
off = 12
while off < n and data[off] != 0:
    off += 1 + data[off]
off += 5
while off + 10 <= n:
    if data[off] & 0xc0 == 0xc0:
        off += 2
    else:
        while off < n and data[off] != 0:
            off += 1 + data[off]
        off += 1
    rtype, _, _, rdlen = struct.unpack('>HHIH', data[off:off + 10])
    off += 10
    if rtype == 1 and rdlen == 4:
        print('.'.join(str(b) for b in data[off:off + 4]))
        break
    off += rdlen
EOF
)"
  if [ "$RESOLVED" != "$HOST_IP" ]; then
    echo "[wpad] DNS 自檢失敗：$WPAD_HOST 解到 $RESOLVED，預期 $HOST_IP" >&2
    exit 1
  fi
fi
