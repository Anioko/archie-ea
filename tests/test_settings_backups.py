"""Settings backups are real repository-managed artefacts, never demo rows."""

from pathlib import Path


def test_backup_service_create_list_download_delete_round_trip(tmp_path, monkeypatch):
    """A successful database dump must become the exact listed/downloaded artefact."""
    from app.services.system_backup_service import SystemBackupService

    def fake_run(command, **kwargs):
        output = Path(command[command.index("--file") + 1])
        output.write_bytes(b"PGDMP\x01real-backup")

    monkeypatch.setattr("app.services.system_backup_service.subprocess.run", fake_run)
    service = SystemBackupService(tmp_path, "postgresql://db/archie")

    created = service.create()
    assert created["size_bytes"] == 17
    assert service.list() == [created]
    assert service.path_for(created["name"]).read_bytes() == b"PGDMP\x01real-backup"

    service.delete(created["name"])
    assert service.list() == []
    assert not service.path_for(created["name"]).exists()


def test_restore_takes_safety_backup_before_replacing_database(tmp_path, monkeypatch):
    """Restore is destructive, so it must first leave a real rollback dump."""
    from app.services.system_backup_service import SystemBackupService

    commands = []

    def fake_run(command, **kwargs):
        commands.append(command)
        if command[0] == "pg_dump":
            Path(command[command.index("--file") + 1]).write_bytes(b"PGDMP-safety")

    monkeypatch.setattr("app.services.system_backup_service.subprocess.run", fake_run)
    source = tmp_path / "backup_20260904T120000Z_12345678.dump"
    source.write_bytes(b"PGDMP-source")
    service = SystemBackupService(tmp_path, "postgresql://db/archie")

    result = service.restore(source.name)

    assert result["restored"] == source.name
    assert result["safety_backup"] != source.name
    assert (tmp_path / result["safety_backup"]).read_bytes() == b"PGDMP-safety"
    assert commands[-1][0] == "pg_restore"
    assert str(source) in commands[-1]


def test_settings_backup_panel_has_no_invented_archives_and_wires_every_action():
    """Removing JS wiring or reintroducing plausible literal rows must fail."""
    template = Path("app/templates/settings/index.html").read_text(encoding="utf-8")

    assert "backup_2024_02_20_1000.zip" not in template
    assert "backup_2024_02_13_1000.zip" not in template
    assert "2.4 MB" not in template
    assert "2.1 MB" not in template
    assert "loadBackups()" in template
    assert "downloadBackup(" in template
    assert "restoreBackup(" in template
    assert "deleteBackup(" in template
    assert "'/api/system-backups'" in template

