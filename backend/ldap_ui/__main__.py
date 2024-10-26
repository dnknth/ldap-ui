import logging

import click
import uvicorn
from uvicorn.config import LOG_LEVELS
from uvicorn.logging import ColourizedFormatter
from uvicorn.main import LEVEL_CHOICES

import ldap_ui

from . import settings


def print_version(ctx: click.Context, param: click.Parameter, value: bool) -> None:
    if value:
        click.echo(ldap_ui.__version__)
        ctx.exit()


@click.command()
@click.option(
    "-b",
    "--base-dn",
    type=str,
    default=settings.BASE_DN,
    help="LDAP base DN (required). [default: BASE_DN environment variable]",
)
@click.option(
    "-h",
    "--host",
    type=str,
    default="127.0.0.1",
    help="Bind socket to this host.",
    show_default=True,
)
@click.option(
    "-p",
    "--port",
    type=int,
    default=5000,
    help="Bind socket to this port. If 0, an available port will be picked.",
    show_default=True,
)
@click.option(
    "-u",
    "--ldap-url",
    type=str,
    help="LDAP directory connection URL. [default: LDAP_URL environment variable or 'ldap:///']",
)
@click.option(
    "-l",
    "--log-level",
    type=LEVEL_CHOICES,
    default="info",
    help="Log level. [default: info]",
    show_default=True,
)
@click.option(
    "--version",
    is_flag=True,
    callback=print_version,
    expose_value=False,
    is_eager=True,
    help="Display the current version and exit.",
)
def main(base_dn, host, port, ldap_url, log_level):
    logging.basicConfig(level=LOG_LEVELS[log_level])
    rootHandler = logging.getLogger().handlers[0]
    rootHandler.setFormatter(ColourizedFormatter(fmt="%(levelprefix)s %(message)s"))

    if base_dn is not None:
        settings.BASE_DN = base_dn

    if ldap_url is not None:
        settings.LDAP_URL = ldap_url

    uvicorn.run(
        "ldap_ui.app:app",
        host=host,
        port=port,
    )


if __name__ == "__main__":
    main()
