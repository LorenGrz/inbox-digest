from inbox_digest.main import cli


def test_should_exit_zero_when_cli_runs_without_commands() -> None:
    assert cli() == 0
