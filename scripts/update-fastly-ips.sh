#!/bin/sh
# 從 https://api.fastly.com/public-ip-list 更新 proxy.pac.template 的 isFastlyIP 區塊
# 用法：scripts/update-fastly-ips.sh [proxy.pac.template]
set -eu
FILE="${1:-proxy.pac.template}"
TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT
curl -fsSL https://api.fastly.com/public-ip-list -o "$TMP"
python3 - "$TMP" "$FILE" <<'PY'
import ipaddress, json, sys
src, dst = sys.argv[1], sys.argv[2]
data = json.load(open(src))
lines = []
for cidr in data["addresses"]:
    net = ipaddress.ip_network(cidr)
    lines.append(f'    isInNet(ip, "{net.network_address}", "{net.netmask}") ||')
if lines:
    lines[-1] = lines[-1].removesuffix(" ||") + ";"
block = "\n".join(lines)
text = open(dst).read()
start = text.index("  return isInNet(ip,")
end = text.index(";", start) + 1
open(dst, "w").write(text[:start] + block + text[end:])
print(f"updated {dst} with {len(lines)} ranges")
PY
