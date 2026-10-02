"""Generated-project contract compatibility: the versions recorded in
prereqai-project.json (contract_version), prereqai-manifest.json
(manifest_version, contract_version) and prereqai-config.json
(config_version) are checked in one place, and a project from another
contract is reported as INCOMPATIBLE with structured details -- never
imported, executed or regenerated over as if it were current."""
import json
import shutil

import pytest

from backend.api_generation import (
    CONFIG_FILENAME,
    INCOMPATIBLE,
    METADATA_FILENAME,
    PROJECT_MANIFEST_FILENAME,
    GeneratedProjectManifest,
    GeneratedProjectMetadata,
    IncompatibleProjectManifestError,
    IncompatibleProjectMetadataError,
    check_generated_project,
)
from backend.cli import EXIT_FAILURE, EXIT_OK, main
from test_generated_project_importability import EXAMPLE

VERSIONS = [  # (file, field)
    (METADATA_FILENAME, "contract_version"),
    (PROJECT_MANIFEST_FILENAME, "manifest_version"),
    (PROJECT_MANIFEST_FILENAME, "contract_version"),
    (CONFIG_FILENAME, "config_version"),
]


@pytest.fixture
def project(tmp_path):
    copy = tmp_path / "project"
    shutil.copytree(EXAMPLE / "generated", copy)
    return copy


def _set(project, file, field, value):
    data = json.loads((project / file).read_text())
    if value is _DROP:
        del data[field]
    else:
        data[field] = value
    (project / file).write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


_DROP = object()


def test_the_committed_example_is_the_current_compatible_contract(capsys):
    health = check_generated_project(EXAMPLE / "generated")
    assert health.healthy and health.findings == []
    assert main(["api-generation", "check", str(EXAMPLE / "generated")]) == EXIT_OK
    capsys.readouterr()


@pytest.mark.parametrize("file, field", VERSIONS)
@pytest.mark.parametrize("value, relation", [(99, "newer"), (0, "older"), (_DROP, "missing"), ("1", "unreadable")])
def test_every_other_version_is_incompatible_with_structured_details(project, file, field, value, relation):
    _set(project, file, field, value)
    (project / "app" / "main.py").write_text("raise SystemExit('must not be imported')\n")  # never executed

    health = check_generated_project(project)

    assert health.status == INCOMPATIBLE and not health.healthy
    incompatible = [f for f in health.findings if f["category"] == "INCOMPATIBLE_PROJECT"]
    assert [f["details"] for f in incompatible] == [{
        "file": file, "field": field, "found": None if value is _DROP else value, "supported": 1, "relation": relation,
    }]
    # nothing after the compatibility gate ran: no import, syntax or OpenAPI findings
    assert {f["category"] for f in health.findings} == {"INCOMPATIBLE_PROJECT"}
    assert {"newer": "newer PreReqAI", "older": "regenerate", "missing": "regenerate", "unreadable": "not an integer"}[
        relation] in incompatible[0]["message"]


def test_cli_check_reports_incompatibility_as_json_and_fails(project, capsys):
    _set(project, METADATA_FILENAME, "contract_version", 2)
    assert main(["api-generation", "check", str(project), "--json"]) == EXIT_FAILURE
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "incompatible"
    assert report["findings"][0]["details"]["relation"] == "newer"


def test_parsers_raise_typed_errors_carrying_the_comparison():
    metadata = json.loads((EXAMPLE / "generated" / METADATA_FILENAME).read_text())
    with pytest.raises(IncompatibleProjectMetadataError) as caught:
        GeneratedProjectMetadata.parse(json.dumps({**metadata, "contract_version": 3}))
    assert caught.value.compatibility["relation"] == "newer"

    manifest = json.loads((EXAMPLE / "generated" / PROJECT_MANIFEST_FILENAME).read_text())
    del manifest["manifest_version"]
    with pytest.raises(IncompatibleProjectManifestError) as caught:
        GeneratedProjectManifest.parse(json.dumps(manifest))
    assert caught.value.compatibility == {"file": PROJECT_MANIFEST_FILENAME, "field": "manifest_version",
                                          "found": None, "supported": 1, "relation": "missing"}


def test_files_of_another_shape_stay_invalid_rather_than_incompatible(project):
    """Only a file that is recognisably this generator's is version-checked:
    unrelated or empty content is a malformed project, not another contract."""
    (project / PROJECT_MANIFEST_FILENAME).write_text("{}")
    categories = {f["category"] for f in check_generated_project(project).findings}
    assert "INVALID_MANIFEST" in categories and "INCOMPATIBLE_PROJECT" not in categories


def test_an_incompatible_project_is_not_regenerated_over_as_generated_output(project, tmp_path, capsys):
    """Without its marker, only a *compatible* prereqai-project.json proves a
    directory is this generator's output; a newer project is left untouched."""
    (project / ".prereqai-generated.json").unlink()
    _set(project, METADATA_FILENAME, "contract_version", 2)
    before = (project / "app" / "main.py").read_bytes()

    assert main(["api-generation", "generate", "--draft", str(EXAMPLE / "draft.json"),
                 "--output-dir", str(project)]) == EXIT_FAILURE
    assert "refusing to overwrite" in capsys.readouterr().err
    assert (project / "app" / "main.py").read_bytes() == before
