import json
import shutil
import subprocess

import pytest
from scripts.deploy.remote import dotenv

pytestmark = pytest.mark.compose


@pytest.mark.skipif(not shutil.which("docker"), reason="Docker Compose CLI is needed for the real dotenv parser")
@pytest.mark.parametrize("value", ["plain", "space Кириллица", "'quoted'", r"back\slash", r"a\'b $HOME $(echo nope) `nope` #tag"])
def test_compose_reads_special_characters_verbatim(tmp_path, value):
    env = tmp_path / "synthetic.env"
    env.write_text(dotenv({"VALUE": value}), encoding="utf-8")
    compose = tmp_path / "compose.yaml"
    compose.write_text('services:\n  example:\n    image: alpine:3.22\n    environment:\n      PAYLOAD: ${VALUE}\n', encoding="utf-8")
    result = subprocess.run(["docker", "compose", "--env-file", str(env), "-f", str(compose), "config", "--format", "json"], capture_output=True, check=True, text=True, encoding="utf-8")
    # `config` escapes literal dollars again so its output can be reused as Compose input.
    assert json.loads(result.stdout)["services"]["example"]["environment"]["PAYLOAD"].replace("$$", "$") == value
