"""PREREQAI_SESSION_DIR set the way env files, systemd and Docker set it (unexpanded ~, blank) still works."""
from backend.session import session_manager


def test_a_home_relative_directory_is_expanded_not_created_literally(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("PREREQAI_SESSION_DIR", "~/sessions")
    monkeypatch.chdir(cwd)
    session_manager.sessions.clear()

    session = session_manager.create("Home paper")
    session_manager.sessions.clear()  # restart

    assert (home / "sessions" / f"{session.session_id}.session").is_file()
    assert not (cwd / "~").exists()
    assert session_manager.get(session.session_id).paper_title == "Home paper"
    assert [s.paper_title for s in session_manager.list()] == ["Home paper"]


def test_a_blank_setting_means_no_persistence_and_a_plain_path_still_works(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PREREQAI_SESSION_DIR", "   ")
    session_manager.sessions.clear()
    session_manager.create("Memory only")
    assert list(tmp_path.iterdir()) == []

    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path / "plain"))
    saved = session_manager.create("Plain path")
    assert (tmp_path / "plain" / f"{saved.session_id}.session").is_file()
