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


def test_configured_source_roots_are_named_and_local(monkeypatch, tmp_path):
    from server.songbook.config import settings_from_environment

    monkeypatch.setenv("SONGBOOK_LIBRARY_ROOT", str(tmp_path / "managed"))
    monkeypatch.setenv("SONGBOOK_SOURCE_ROOTS", f'{{"music": "{tmp_path}"}}')
    settings = settings_from_environment()
    assert settings.library_root == tmp_path / "managed"
    assert settings.source_roots == {"music": tmp_path}
