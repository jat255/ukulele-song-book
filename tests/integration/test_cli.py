from server.songbook.cli import main
from server.songbook.config import Settings
from server.songbook.main import create_app


def test_password_provisioning_and_session_revocation(tmp_path, monkeypatch):
    monkeypatch.setenv("SONGBOOK_LIBRARY_ROOT", str(tmp_path))
    answers = iter(["a sufficiently long password", "a sufficiently long password"])
    monkeypatch.setattr("getpass.getpass", lambda prompt: next(answers))
    assert main(["auth", "set-password"]) == 0
    app = create_app(Settings(library_root=tmp_path))
    token, _ = app.state.auth.authenticate("a sufficiently long password", "local")
    assert app.state.auth.principal(token)


def test_password_confirmation_mismatch_does_not_create_credentials(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("SONGBOOK_LIBRARY_ROOT", str(tmp_path))
    answers = iter(["a sufficiently long password", "a different long password"])
    monkeypatch.setattr("getpass.getpass", lambda prompt: next(answers))
    assert main(["auth", "set-password"]) != 0
    assert not (tmp_path / "library.sqlite").exists()
