"""
Theme configurations for AgentOpsCLI terminal UI.
"""

from dataclasses import dataclass


@dataclass
class Theme:
    name: str
    primary: str
    secondary: str
    accent: str
    success: str
    warning: str
    danger: str
    muted: str
    background: str


DARK_THEME = Theme(
    name="dark",
    primary="bold cyan",
    secondary="bright_blue",
    accent="magenta",
    success="bold green",
    warning="bold yellow",
    danger="bold red",
    muted="dim white",
    background="black",
)

LIGHT_THEME = Theme(
    name="light",
    primary="bold blue",
    secondary="navy_blue",
    accent="dark_magenta",
    success="bold green",
    warning="dark_orange",
    danger="bold red",
    muted="dim black",
    background="white",
)

THEMES = {
    "dark": DARK_THEME,
    "light": LIGHT_THEME,
}


def get_theme(name: str = "dark") -> Theme:
    return THEMES.get(name.lower(), DARK_THEME)

