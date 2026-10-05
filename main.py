"""Regenerate the WA1 holder from the supplied button and display case meshes."""

from cad.configuration import ButtonHolderConfig
from cad.export_button_holder import run


def main() -> None:
    """Configure and start button/display-holder generation.

    :return: None.
    """
    config: ButtonHolderConfig = ButtonHolderConfig()
    run(config)


if __name__ == "__main__":
    main()
