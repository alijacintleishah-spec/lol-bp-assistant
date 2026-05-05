"""
LCU 全面诊断脚本 —— 测试所有可能的 champ select 相关端点。
运行方式: python lcu_diag.py
"""
import base64, json, ssl, time
import requests
import urllib3
urllib3.disable_warnings()

# 复用 lcu.py 的进程检测
from lcu import find_lcu_process

print("=" * 60)
print("  LCU 全面诊断")
print("=" * 60)

# 1. 找进程
print("\n[1] 查找 LCU 进程...")
port, token = find_lcu_process()
if not port:
    print("❌ 未找到 LCU 进程！请确保 LoL 客户端已启动。")
    exit(1)

print(f"✅ 找到端口: {port}")
print(f"   Token: {token[:20]}...")

auth = base64.b64encode(f"riot:{token}".encode()).decode()
headers = {
    "Authorization": f"Basic {auth}",
    "Accept": "application/json"
}
base = f"https://127.0.0.1:{port}"

# 2. 测试基础连接
print("\n[2] 测试基础连接...")
try:
    r = requests.get(f"{base}/riotclient/ux-state", headers=headers, verify=False, timeout=5)
    print(f"   /riotclient/ux-state → {r.status_code}")
except Exception as e:
    print(f"   /riotclient/ux-state → 失败: {e}")

# 3. 测试各种 champ-select 端点
print("\n[3] 测试 champ-select 端点...")
endpoints = [
    "/lol-champ-select/v1/session",
    "/lol-champ-select/v2/session",
    "/lol-champ-select/v1/session/selection",
    "/lol-champ-select/v1/pin",
    "/lol-champ-select/v1/all-grid-champions",
    "/lol-champ-select/v1/pickable-champion-ids",
    "/lol-champ-select/v1/bannable-champion-ids",
]
for ep in endpoints:
    try:
        r = requests.get(f"{base}{ep}", headers=headers, verify=False, timeout=5)
        status = r.status_code
        if status == 200:
            try:
                body = r.text[:150]
            except:
                body = "(binary)"
            print(f"   {ep} → {status} ✅ body: {body}")
        else:
            print(f"   {ep} → {status}")
    except Exception as e:
        print(f"   {ep} → 异常: {e}")

# 4. 测试 gameflow 端点
print("\n[4] 测试 gameflow 端点...")
gf_endpoints = [
    "/lol-gameflow/v1/gameflow-phase",
    "/lol-gameflow/v1/session",
    "/lol-gameflow/v1/availability",
    "/lol-gameflow/v1/basic-tutorial",
]
for ep in gf_endpoints:
    try:
        r = requests.get(f"{base}{ep}", headers=headers, verify=False, timeout=5)
        status = r.status_code
        if status == 200:
            body = r.text[:200]
            print(f"   {ep} → {status} ✅ body: {body}")
        else:
            print(f"   {ep} → {status}")
    except Exception as e:
        print(f"   {ep} → 异常: {e}")

# 5. 测试 Swagger/OpenAPI 文档
print("\n[5] 测试 API 文档...")
for ep in ["/swagger/v3/openapi.json", "/swagger/v2/api-docs", "/api-docs"]:
    try:
        r = requests.get(f"{base}{ep}", headers=headers, verify=False, timeout=5)
        print(f"   {ep} → {r.status_code}")
    except Exception as e:
        print(f"   {ep} → 异常: {e}")

# 6. 测试 summoner 端点（确认 LCU 正常工作）
print("\n[6] 测试召唤师信息...")
try:
    r = requests.get(f"{base}/lol-summoner/v1/current-summoner", headers=headers, verify=False, timeout=5)
    if r.status_code == 200:
        data = r.json()
        print(f"   ✅ 召唤师: {data.get('displayName', '?')} (等级 {data.get('summonerLevel', '?')})")
    else:
        print(f"   /lol-summoner/v1/current-summoner → {r.status_code}")
except Exception as e:
    print(f"   异常: {e}")

# 7. WebSocket 测试
print("\n[7] WebSocket 连接测试...")
try:
    import websocket
    ws_url = f"wss://127.0.0.1:{port}/"
    ws = websocket.WebSocket(sslopt={"cert_reqs": ssl.CERT_NONE})
    ws.connect(ws_url, header={"Authorization": f"Basic {auth}"}, timeout=5)
    print(f"   ✅ WebSocket 已连接")

    # 订阅事件
    ws.send(json.dumps([5, "OnJsonApiEvent"]))
    print(f"   ✅ 已订阅 OnJsonApiEvent")

    # 等待 3 秒看是否有 champ-select 事件
    print("   等待 3 秒收集事件...")
    ws.settimeout(3)
    events = []
    deadline = time.time() + 3
    while time.time() < deadline:
        try:
            msg = ws.recv()
            event = json.loads(msg)
            if isinstance(event, list) and len(event) >= 3:
                uri = event[2].get("uri", "") if isinstance(event[2], dict) else ""
                if "champ" in uri.lower():
                    events.append({"uri": uri, "type": event[2].get("eventType", "?")})
        except websocket.WebSocketTimeoutException:
            break
        except Exception:
            break

    if events:
        print(f"   ✅ 收到 {len(events)} 个 champ-select 事件:")
        for e in events:
            print(f"      - {e}")
    else:
        print("   ℹ 未收到 champ-select 事件 (可能在 lobby，不在选人阶段)")

    ws.close()
except ImportError:
    print("   ⚠ websocket-client 未安装")
except Exception as e:
    print(f"   ❌ WebSocket 失败: {e}")

print("\n" + "=" * 60)
print("  诊断完成。请将以上输出完整复制发给我。")
print("=" * 60)
