from pathlib import Path

import yaml


def test_ci_triggers_and_lightweight_quick_jobs():
    # BaseLoader avoids YAML 1.1 treating the GitHub `on` key as a boolean.
    quick = yaml.load(Path(".github/workflows/quick.yml").read_text(), Loader=yaml.BaseLoader)
    full = yaml.load(Path(".github/workflows/full.yml").read_text(), Loader=yaml.BaseLoader)
    assert set(quick["on"]) == {"push", "pull_request"}
    assert quick["on"]["push"]["branches"] == ["main"]
    assert all(not path.startswith("docs") for path in quick["on"]["push"]["paths"])
    assert set(full["on"]) == {"workflow_dispatch"}
    commands = " ".join(step.get("run", "") for job in quick["jobs"].values() for step in job["steps"])
    assert "stack" not in commands and "playwright" not in commands and "test:full" not in commands
    assert "not compose and not ssh" in commands


def test_compose_keeps_original_persistent_volume_names():
    compose = yaml.safe_load(Path("infra/compose/compose.yaml").read_text())
    assert compose["name"] == "${COMPOSE_PROJECT_NAME:-refraction}"
    assert compose["volumes"] == {
        "postgres": {"name": "${COMPOSE_PROJECT_NAME:-refraction}_postgres"},
        "uploads": {"name": "${COMPOSE_PROJECT_NAME:-refraction}_uploads"},
    }
