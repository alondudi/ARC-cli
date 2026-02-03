import click
from aws_manager import AWSClient


@click.group()
def arc():
    """ARC - Amazon Resources Controller CLI"""
    pass


###########AWS-SETUP#############
@arc.command()
def setup():
    """Configure and save AWS credentials"""
    click.echo("Checking for existing credentials...")
    manager = AWSClient()
    is_ok, info = manager.validate_connection()

    if is_ok:
        click.secho(f"Already connected as: {info}", fg='green')
        return

    access_key = click.prompt("Enter AWS Access Key")
    secret_key = click.prompt("Enter AWS Secret Key", hide_input=True)
    region = click.prompt("Enter preferred region", default="us-east-1")
    new_manager = AWSClient(access_key, secret_key, region)
    is_ok_new, result = new_manager.validate_connection()

    if is_ok_new:
        new_manager.save_config(access_key, secret_key, region)
        click.secho("Connected and saved successfully!", fg='green', bold=True)
    else:
        click.secho(f"Failed: {result}", fg='red')


@arc.command()
def profile():
    """Show current identity"""
    manager = AWSClient()
    is_ok, info = manager.validate_connection()
    if is_ok:
        click.secho(f"Current Identity: {info}", fg='cyan')
    else:
        click.secho(f"Not connected: {info}", fg='red')


#############LIST###############
@arc.group()
def list():
    """List AWS resources (s3, ec2, Route53, etc.)"""
    pass


@list.command(name="s3")
def list_s3():
    """List only S3 buckets created by ARC"""
    click.echo("Fetching ARC-managed buckets... ")
    manager = AWSClient()
    buckets = manager.get_arc_buckets()
    if not buckets:
        click.echo("No ARC buckets found.")
        return
    click.secho("-----ARC-buckets-----", fg="bright_blue")
    for bucket in buckets:
        click.echo(f" • {bucket} [Managed by ARC]")


@list.command(name="ec2")
def list_ec2():
    """List all EC2 instances"""
    click.echo("Fetching EC2 instances...")
    click.echo("Feature coming soon!")

#############create###############
@arc.group()
def create():
    """List AWS resources (s3, ec2, Route53, etc.)"""
    pass


@create.command(name="s3")
@click.argument('name')
@click.option('--public', is_flag=True, help="Make the bucket public")
def create_s3(name, public):
    """Create a new S3 bucket with security confirmation"""
    if public:
        click.secho("WARNING: You are about to create a PUBLIC bucket.", fg='yellow', bold=True)
        click.secho("This means anyone on the internet can potentially see your files.", fg='yellow')
        if not click.confirm("Are you absolutely sure you want to proceed?"):
            click.echo("Operation aborted. Your security is important")
            return
    click.echo(f"Creating bucket '{name}'...")
    manager = AWSClient()
    success, message = manager.create_bucket(name, is_public=public)
    if success:
        click.secho(f"{message}", fg='green', bold=True)
    else:
        click.secho(f"Error: {message}", fg='red')


@arc.group()
def delete():
    """Delete AWS resources (s3, etc.)"""
    pass


@delete.command(name="s3")
@click.argument('name')
def delete_s3(name):
    """Delete an ARC-managed S3 bucket"""
    # קונפירמציה היא חובה במחיקה!
    if not click.confirm(f"Are you SURE you want to delete '{name}'? This cannot be undone."):
        click.echo("Delete aborted.")
        return

    manager = AWSClient()
    success, message = manager.delete_bucket(name)

    if success:
        click.secho(f"{message}", fg='green', bold=True)
    else:
        click.secho(f"Error: {message}", fg='red')


@arc.group()
def upload():
    """Upload resources to AWS"""
    pass


@upload.command(name="s3")
@click.argument('file_path', type=click.Path(exists=True))  # בודק שהקובץ קיים פיזית
@click.argument('bucket_name')
def upload_s3(file_path, bucket_name):
    """Upload files to an ARC-managed S3 bucket"""
    click.echo(f"Uploading '{file_path}' to '{bucket_name}'...")
    manager = AWSClient()
    success, message = manager.upload_to_s3(file_path, bucket_name)

    if success:
        click.secho(f"{message}", fg='green', bold=True)
        url = f"https://{bucket_name}.s3.{manager.region}.amazonaws.com/{import_os_basename(file_path)}"
        click.echo(f"Public Link (if public): {url}")
    else:
        click.secho(f"Error: {message}", fg='red')


def import_os_basename(path):
    import os
    return os.path.basename(path)