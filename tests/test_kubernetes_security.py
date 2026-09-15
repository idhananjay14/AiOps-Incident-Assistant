from pathlib import Path

import yaml

K8S_ROOT = Path(__file__).parents[1] / "k8s"


def load_manifests(path: Path) -> list[dict]:
    with path.open() as file:
        return [manifest for manifest in yaml.safe_load_all(file) if manifest]


def container_security(manifest: dict) -> dict:
    return manifest["spec"]["template"]["spec"]["containers"][0]["securityContext"]


def test_application_workloads_run_securely():
    workloads = [
        K8S_ROOT / "app" / "deployment.yaml",
        K8S_ROOT / "incident-api" / "deployment.yaml",
        K8S_ROOT / "migration" / "job.yaml",
    ]

    for path in workloads:
        for manifest in load_manifests(path):
            if "template" not in manifest.get("spec", {}):
                continue

            pod_spec = manifest["spec"]["template"]["spec"]
            security = container_security(manifest)

            assert pod_spec.get("hostNetwork", False) is False
            assert pod_spec.get("hostPID", False) is False
            assert pod_spec.get("hostIPC", False) is False

            assert security["runAsNonRoot"] is True
            assert security["runAsUser"] == 1000
            assert security["allowPrivilegeEscalation"] is False
            assert security["capabilities"]["drop"] == ["ALL"]
            assert security.get("privileged", False) is False


def test_application_pods_do_not_mount_service_account_tokens():
    for path in [
        K8S_ROOT / "app" / "deployment.yaml",
        K8S_ROOT / "incident-api" / "deployment.yaml",
    ]:
        for manifest in load_manifests(path):
            if "template" not in manifest.get("spec", {}):
                continue

            pod_spec = manifest["spec"]["template"]["spec"]

            assert pod_spec["automountServiceAccountToken"] is False
