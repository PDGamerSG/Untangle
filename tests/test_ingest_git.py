"""git_history: log parsing (renames, binaries, reverts), HEAD listing and batched blob reads on a tmp repo."""

from __future__ import annotations

import pytest

from ingest_fixture import DATES_MS, build_repo
from kyun.ingest.git_history import GitRepo, detect_revert, parse_log


@pytest.fixture(scope="module")
def repo(tmp_path_factory):
    path = tmp_path_factory.mktemp("repo")
    shas = build_repo(path)
    return GitRepo(path), shas


def test_log_parses_counts_renames_binaries_and_reverts(repo):
    git, shas = repo
    commits = git.log()
    assert [c.sha for c in commits] == [shas[f"c{i}"] for i in (6, 5, 4, 3, 2, 1)]
    by = {c.sha: c for c in commits}
    c1 = by[shas["c1"]]
    assert c1.title == "initial import" and c1.authored_at == DATES_MS[0] and c1.author_email == "ada@example.com"
    logo = next(f for f in c1.files if f.path == "logo.png")
    assert logo.change == "A" and logo.binary and logo.additions is None
    yaml_ = next(f for f in c1.files if f.path == "config/app.yaml")
    assert (yaml_.change, yaml_.additions, yaml_.deletions) == ("A", 3, 0)
    c4 = by[shas["c4"]]
    assert [(f.path, f.change, f.old_path) for f in c4.files] == [("cmd/server.go", "R", "cmd/main.go")]
    c5 = by[shas["c5"]]
    assert c5.is_revert and c5.reverts_sha == shas["c2"] and c5.title == 'Revert "Raise retry limit"'
    assert not any(c.is_merge for c in commits)
    assert by[shas["c2"]].additions == 2 and by[shas["c2"]].deletions == 2 and by[shas["c2"]].files_changed == 2


def test_log_limits(repo):
    git, shas = repo
    assert [c.sha for c in git.log(max_commits=2)] == [shas["c6"], shas["c5"]]
    assert [c.sha for c in git.log(since="2024-04-15")] == [shas["c6"], shas["c5"]]


def test_files_at_head_and_show_many(repo):
    git, shas = repo
    files = git.files_at_head()
    assert set(files) == {"config/app.yaml", "config.toml", "go.mod", "cmd/server.go", "README.md", "docs/adr/0001-use-postgres.md", "docs/adr/0002-switch-to-pgx.md", "logo.png"}
    assert files["logo.png"] == 11
    content = git.show_many([(shas["c1"], "config/app.yaml"), (shas["c2"], "config/app.yaml"), (shas["c1"], "nope.txt"), ("HEAD", "cmd/server.go")])
    assert content[(shas["c1"], "config/app.yaml")] == "app:\n  retry_limit: 3\n  name: demo\n"
    assert "retry_limit: 5" in content[(shas["c2"], "config/app.yaml")]
    assert content[(shas["c1"], "nope.txt")] is None
    assert "healthz" in content[("HEAD", "cmd/server.go")]
    assert git.show_many([("HEAD", "README.md")], max_bytes=5) == {("HEAD", "README.md"): None}
    assert git.default_branch() == "main" and git.head_sha() == shas["c6"]
    assert git.read_at(["README.md", "missing.md"]) == {"README.md": "# Demo\n\nA demo repository for the ingestion tests.\n"}


def test_parse_log_handles_brace_renames_and_quoted_paths():
    rs, us = "\x1e", "\x1f"
    header = us.join(["a" * 40, "b" * 40, "Ann", "ANN@X.IO", "Ann", "ann@x.io", "1700000000", "1700000001", "move things", "move things\n\nbody"])
    text = (
        f"{rs}{header}{us}\n"
        ":100644 100644 1111111 2222222 R090\tsrc/old/util.go\tsrc/new/util.go\n"
        ":000000 100644 0000000 3333333 A\t\"sp\\303\\244ce.txt\"\n"
        ":100644 000000 4444444 0000000 D\tgone.md\n"
        "3\t1\tsrc/{old => new}/util.go\n"
        "-\t-\t\"sp\\303\\244ce.txt\"\n"
        "0\t12\tgone.md\n"
    )
    [c] = parse_log(text)
    assert c.author_email == "ann@x.io" and c.authored_at == 1700000000000 and c.title == "move things"
    changes = {f.path: f for f in c.files}
    assert changes["src/new/util.go"].change == "R" and changes["src/new/util.go"].old_path == "src/old/util.go"
    assert (changes["src/new/util.go"].additions, changes["src/new/util.go"].deletions) == (3, 1)
    assert changes["späce.txt"].change == "A" and changes["späce.txt"].binary
    assert changes["gone.md"].change == "D" and changes["gone.md"].deletions == 12
    assert c.is_merge is False and c.parents == ["b" * 40]


def test_detect_revert():
    assert detect_revert('Revert "x"\n\nThis reverts commit abcdef1234567.') == (True, "abcdef1234567")
    assert detect_revert('Revert "x"') == (True, None)
    assert detect_revert("Fix revert handling") == (False, None)
