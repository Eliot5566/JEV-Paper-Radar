"""action.yml stays a working composite action.

These are plain-text checks on purpose: PyYAML is not a dev dependency,
so the tests must not import it. Real YAML validation happens separately
(python -c 'import yaml; yaml.safe_load(...)'), and the action's run step
is exercised end to end in the PR verification, not here.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACTION = (ROOT / "action.yml").read_text(encoding="utf-8")


def test_action_is_composite_with_python_setup():
    assert 'using: "composite"' in ACTION
    assert "actions/setup-python@v5" in ACTION
    assert 'python-version: "3.12"' in ACTION


def test_action_installs_itself_from_its_own_checkout():
    # When used as `uses: owner/repo@ref`, GITHUB_ACTION_PATH is the
    # checked-out action repository, so this installs the action itself.
    assert 'python -m pip install "${GITHUB_ACTION_PATH}"' in ACTION


def test_action_declares_the_inputs_the_readme_documents():
    for name in (
        "config:",
        "command:",
        "backend:",
        "limit:",
        "typesafe-api-key:",
        "openrouter-api-key:",
        "anthropic-api-key:",
        "args:",
    ):
        assert name in ACTION, f"missing input {name}"


def test_action_passes_keys_only_as_env_and_never_prints_them():
    assert "TYPESAFE_API_KEY: ${{ inputs.typesafe-api-key }}" in ACTION
    assert "OPENROUTER_API_KEY: ${{ inputs.openrouter-api-key }}" in ACTION
    assert "ANTHROPIC_API_KEY: ${{ inputs.anthropic-api-key }}" in ACTION
    # The only echo in the run step is the command name and config path.
    assert "echo \"Running: paper-radar" in ACTION
    for secret in ("TYPESAFE_API_KEY", "OPENROUTER_API_KEY", "ANTHROPIC_API_KEY"):
        assert f"echo ${secret}" not in ACTION
        assert f"echo ${{{secret}}}" not in ACTION


def test_action_supports_both_commands():
    assert 'paper-radar "${{ inputs.command }}" -c "${{ inputs.config }}"' in ACTION
    assert '--backend "${{ inputs.backend }}"' in ACTION
    assert '--limit "${{ inputs.limit }}"' in ACTION
