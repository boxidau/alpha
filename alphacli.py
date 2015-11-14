import click
import os
from alpha import Alpha

@click.group()
def cli():
    pass

@cli.command()
@click.argument('project_dir', default=os.getcwd())
@click.option('--single', is_flag=True, default=False)
def push(project_dir, single):
    alpha = Alpha()
    if single:
        alpha.push_single(project_dir)
    else:
        alpha.push_all(project_dir)

@cli.command()
@click.argument('alias', required=True)
@click.argument('project_dir', default=os.getcwd())
def promote(project_dir, alias):
    alpha = Alpha()
    alpha.promote_all(project_dir, alias)

if __name__ == '__main__':
    cli()