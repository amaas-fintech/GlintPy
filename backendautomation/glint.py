import click
import subprocess
from .scripts.new_stack import stack_automate
from .scripts.lambdas import lambda_automate


@click.command()
@click.option('--file', prompt='Provide the path of package.json file')
def master_command(file=''):
    lambda_automate(file)
    stack_automate(file)

if __name__ == '__main__':
    master_command()