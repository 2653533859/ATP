# Android Docker Worker Connectivity Rehearsal

> Date: 2026-07-10
> Host: macOS / Docker Desktop
> Result: Worker ADB binary and host ADB-server control path verified; no physical Android device was attached, so device shell/data-plane verification remains environment-specific.

## Supported Topologies

### Direct Device TCP

Use this when the worker container can route to the Android device's LAN address.

1. On the host, authorize the device over USB and run `adb tcpip 5555`.
2. Determine the device LAN IP.
3. From the worker container, independently run `adb connect <device-ip>:5555`.
4. Verify `adb -s <device-ip>:5555 get-state` and `adb -s <device-ip>:5555 shell 'echo ok'`.

The host's `adb connect` state is not automatically shared with the container. Host pre-connect is useful for authorization/testing, but the container has its own ADB server unless `ADB_SERVER_SOCKET` is configured.

### Shared Host ADB Server

Use this when the host owns USB devices or already maintains TCP connections.

```bash
export ADB_SERVER_SOCKET=tcp:host.docker.internal:5037
```

The host ADB server must be reachable from the container. Docker Desktop can forward `host.docker.internal` to host services. Linux requires the Compose `host-gateway` mapping and an ADB server/proxy listening on a host-reachable address; the default `127.0.0.1:5037` bind is usually insufficient on native Linux.

Exposing ADB server port 5037 grants powerful device control. Restrict it to the Docker host/bridge, firewall external access, and never publish it broadly.

## Rehearsal Evidence

Available worker image:

```text
atp-worker:q11-readiness
```

Worker-local ADB check:

```bash
docker run --rm --entrypoint sh atp-worker:q11-readiness -lc \
  'adb version; command -v adb; getent hosts host.docker.internal; adb devices -l'
```

Observed:

```text
Android Debug Bridge version 1.0.41
Version 29.0.6-debian
/usr/bin/adb
host.docker.internal resolved to the Docker Desktop host gateway
container-local adb server started successfully
device list empty
```

Shared host-server check:

```bash
docker run --rm \
  --add-host=host.docker.internal:host-gateway \
  -e ADB_SERVER_SOCKET=tcp:host.docker.internal:5037 \
  --entrypoint adb \
  atp-worker:q11-readiness devices -l
```

Observed: command exited `0` and returned the host ADB server device list, which was empty because no physical device was connected. No container-local daemon startup message appeared, confirming the client used the configured external server.

## Full Device Verification

For direct TCP mode:

```bash
docker run --rm \
  --add-host=host.docker.internal:host-gateway \
  -v "$PWD/scripts/android-network-doctor.sh:/usr/local/bin/android-network-doctor:ro" \
  --entrypoint bash \
  atp-worker:q11-readiness \
  /usr/local/bin/android-network-doctor <device-ip>:5555
```

For shared host-server mode with an existing USB or TCP serial:

```bash
docker run --rm \
  --add-host=host.docker.internal:host-gateway \
  -e ADB_SERVER_SOCKET=tcp:host.docker.internal:5037 \
  -e ADB_SKIP_SERVER_RESTART=true \
  -e ADB_SKIP_CONNECT=true \
  -v "$PWD/scripts/android-network-doctor.sh:/usr/local/bin/android-network-doctor:ro" \
  --entrypoint bash \
  atp-worker:q11-readiness \
  /usr/local/bin/android-network-doctor <existing-serial>
```

Acceptance requires all doctor checks to pass, including device state and `shell echo: ok`. Capture the serial, image digest, host platform, network topology, and output without recording device secrets.

## Platform Constraints

| Platform | Direct device IP | Shared host ADB server | `network_mode: host` |
| --- | --- | --- | --- |
| Docker Desktop macOS/Windows | Works when VM can route to device LAN; Wi-Fi/VPN isolation may block | `host.docker.internal:5037` is preferred when host service forwarding is available | Not equivalent to native Linux host networking |
| Native Linux Docker | Usually works when routing/firewall permit device IP | Add `host.docker.internal:host-gateway`; host ADB must listen beyond loopback or use a restricted proxy | Possible, but Compose service DNS/ports and dependency endpoints must be redesigned |
| Kubernetes | Depends on node/device routing and security policy | No portable `host.docker.internal`; use a dedicated, secured ADB gateway | Host networking is cluster-specific and not the default ATP Helm topology |

Do not enable `network_mode: host` casually in the current Compose stack. The worker also needs PostgreSQL, Redis, MinIO, Jaeger, and metrics connectivity; switching network namespaces can break Compose DNS and create host-port conflicts.

## Port Clarification

- `5037`: ADB server control socket.
- `<device-ip>:5555`: Android device adbd TCP endpoint.
- Host `5555` in the current Compose app: Flower UI.

Therefore `host.docker.internal:5555` normally reaches Flower, not an Android device or ADB server. Use the actual device IP for direct mode or port 5037 for shared-server mode.

## Operational Checklist

- Worker image contains `/usr/bin/adb` and reports its version.
- Chosen topology is explicit: direct device or shared host server.
- Container can resolve/reach its target without exposing ADB to untrusted networks.
- `adb devices -l` shows exactly the intended serial as `device`, not `offline` or `unauthorized`.
- `adb -s <serial> shell 'echo ok'` succeeds.
- ATP device scan records the same serial and online state.
- One controlled Android case produces a terminal run and expected artifact.
- ADB reconnect/heartbeat metrics show no unexplained failure spike.

Related documentation: `docs/android-device-debugging.md`, `docs/celery-queues.md`, and `docs/worker-lifecycle.md`.
