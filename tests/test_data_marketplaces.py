"""Tests for copilotsetup.data.marketplaces — marketplace provider."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from copilotsetup.data.marketplaces import MarketplaceInfo, MarketplaceProvider


def _mock_result(stdout: str, returncode: int = 0) -> MagicMock:
    return MagicMock(returncode=returncode, stdout=stdout)


@patch("copilotsetup.data.marketplaces.run_copilot")
def test_parses_builtin_and_registered(run_copilot):
    run_copilot.return_value = _mock_result(
        """✨ Included with GitHub Copilot:
  ◆ copilot-plugins (GitHub: github/copilot-plugins)
  ◆ awesome-copilot (GitHub: github/awesome-copilot)

Registered marketplaces:
  • my-marketplace (Local: C:\\Users\\me\\repos\\marketplace)
  • other-mkt (GitHub: org/other-mkt)
"""
    )

    items = MarketplaceProvider().load()

    assert len(items) == 4
    assert all(isinstance(item, MarketplaceInfo) for item in items)
    assert items[0].name == "copilot-plugins"
    assert items[0].source == "GitHub: github/copilot-plugins"
    assert items[0].marketplace_type == "builtin"
    assert items[1].name == "awesome-copilot"
    assert items[1].source == "GitHub: github/awesome-copilot"
    assert items[1].marketplace_type == "builtin"
    assert items[2].name == "my-marketplace"
    assert items[2].source == r"Local: C:\Users\me\repos\marketplace"
    assert items[2].marketplace_type == "registered"
    assert items[3].name == "other-mkt"
    assert items[3].source == "GitHub: org/other-mkt"
    assert items[3].marketplace_type == "registered"


@patch("copilotsetup.data.marketplaces.run_copilot")
def test_parses_ansi_decorated_output(run_copilot):
    run_copilot.return_value = _mock_result(
        "\x1b[35m✨ Included with GitHub Copilot:\x1b[0m\n"
        "  \x1b[1m◆\x1b[0m copilot-plugins (GitHub: github/copilot-plugins)\n"
        "\n"
        "\x1b[36mRegistered marketplaces:\x1b[0m\n"
        "  \x1b[32m•\x1b[0m my-marketplace (Local: C:\\Users\\me\\repos\\marketplace)\n"
    )

    items = MarketplaceProvider().load()

    assert items == [
        MarketplaceInfo(
            name="copilot-plugins",
            source="GitHub: github/copilot-plugins",
            marketplace_type="builtin",
        ),
        MarketplaceInfo(
            name="my-marketplace",
            source=r"Local: C:\Users\me\repos\marketplace",
            marketplace_type="registered",
        ),
    ]


@patch("copilotsetup.data.marketplaces.run_copilot")
def test_empty_on_no_output(run_copilot):
    run_copilot.return_value = _mock_result("")

    assert MarketplaceProvider().load() == []


@patch("copilotsetup.data.marketplaces.run_copilot")
def test_empty_on_nonzero_exit(run_copilot):
    run_copilot.return_value = _mock_result("ignored", returncode=1)

    assert MarketplaceProvider().load() == []


@patch("copilotsetup.data.marketplaces.run_copilot")
def test_empty_on_file_not_found(run_copilot):
    run_copilot.side_effect = FileNotFoundError

    assert MarketplaceProvider().load() == []


@patch("copilotsetup.data.marketplaces.run_copilot")
def test_unknown_glyph_falls_back(run_copilot):
    run_copilot.return_value = _mock_result("  ★ weird-mkt (Custom: foo)\n")

    assert MarketplaceProvider().load() == []
