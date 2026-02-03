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
        click.secho("No ARC buckets found.", fg="bright_yellow")
        return
    click.secho("     -----ARC-buckets-----", fg="bright_blue")
    for bucket in buckets:
        click.echo(f" • {bucket} [Managed by ARC]")


@list.command(name="ec2")
def list_ec2():
    """List ARC instances with IP addresses"""
    click.echo("Fetching ARC-managed instances... 🔍")
    manager = AWSClient()
    instances = manager.get_arc_instances()

    if not instances:
        click.echo("No ARC-managed instances found.")
        return

    # כותרת טבלה
    click.secho("                          -----ARC-instances-----", fg="bright_blue")
    header = f"{'NAME':<15} | {'STATUS':<10} | {'PUBLIC IP':<15} | {'PRIVATE IP':<15} | {'ID':<20}"
    click.secho(header, bold=True, underline=True)
    for ins in instances:
        # צביעת סטטוס
        status_color = 'green' if ins['status'] == 'running' else 'yellow' if ins['status'] == 'stopped' else 'white'
        status_text = click.style(ins['status'], fg=status_color)

        # צביעת ה-IP הציבורי (כדי שיבלוט שאפשר להתחבר)
        public_ip = click.style(ins['public_ip'], fg='cyan') if ins['public_ip'] != 'N/A' else ins['public_ip']

        line = f"{ins['name']:<15} | {status_text:<19} | {public_ip:<24} | {ins['private_ip']:<15} | {ins['id']:<20}"
        click.echo(line)
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


@create.command(name="ec2")
@click.argument('name')
def create_ec2(name):
    """Interactive EC2 creation wizard with Quota management"""

    # 1. בחירת מערכת הפעלה
    os_choice = click.prompt(
        "Which OS would you like?",
        type=click.Choice(['AL2023', 'UBUNTU'], case_sensitive=False),
        default='AL2023'
    )

    # 2. בחירת גודל שרת (T3 Micro vs T3 Small)
    size_choice = click.prompt(
        "Choose instance size",
        type=click.Choice(['t3.micro', 't3.small'], case_sensitive=False),
        default='t3.micro'
    )

    # 3. הוספת User Data
    user_data = None
    if click.confirm("Would you like to add a User Data script?"):
        click.echo("Enter your script (type 'END' on a new line to finish):")
        lines = []
        while True:
            line = input()
            if line.strip().upper() == 'END':
                break
            lines.append(line)
        user_data = "\n".join(lines)

    # 4. אישור סופי והרצה
    if not click.confirm(f"Launch {os_choice} ({size_choice}) instance '{name}'?"):
        click.echo("Aborted.")
        return

    manager = AWSClient()
    success, message = manager.create_instance(name, os_choice, size_choice, user_data)

    if success:
        click.secho(f"✅ {message}", fg='green', bold=True)
    else:
        click.secho(f"❌ Error: {message}", fg='red')


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