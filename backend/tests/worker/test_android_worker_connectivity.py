import yaml


def test_worker_image_and_compose_expose_adb_connectivity_primitives(repo_file):
    dockerfile = repo_file("backend/Dockerfile.worker")
    compose = yaml.safe_load(repo_file("docker-compose.yml"))
    worker = compose["services"]["worker"]

    assert "android-tools-adb" in dockerfile
    assert "host.docker.internal:host-gateway" in worker["extra_hosts"]


def test_network_doctor_can_preserve_shared_host_adb_server(repo_file):
    script = repo_file("scripts/android-network-doctor.sh")

    assert "ADB_SKIP_SERVER_RESTART" in script
    assert "ADB_SKIP_CONNECT" in script
    assert "adb kill-server" in script
    assert 'adb -s "$TARGET" shell' in script


def test_connectivity_rehearsal_distinguishes_adb_ports_and_topologies(repo_file):
    content = repo_file("docs/android-worker-connectivity-rehearsal.md")

    for marker in (
        "Direct Device TCP",
        "Shared Host ADB Server",
        "ADB_SERVER_SOCKET=tcp:host.docker.internal:5037",
        "<device-ip>:5555",
        "Host `5555` in the current Compose app: Flower UI",
        "device shell/data-plane verification remains environment-specific",
        "ADB_SKIP_SERVER_RESTART=true",
        "ADB_SKIP_CONNECT=true",
    ):
        assert marker in content

    assert "host's `adb connect` state is not automatically shared" in content
    assert "Do not enable `network_mode: host` casually" in content
