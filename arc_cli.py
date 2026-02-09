import click
from services import AWSClient
from rich.console import Console
from rich import box
import sys
import os

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')
    os.system('color')

console = Console()
ARC_LOGO = r"""
    _     ____    ____ 
   / \   |  _ \  / ___|
  / _ \  | |_) || |    
 / ___ \ |  _ < | |___ 
/_/   \_\|_| \_\ \____|

   - MADE BY ALON -"""


@click.group()
def arc():
    """ARC - Amazon Resources Controller CLI"""

    pass


@arc.command()
def easter():
    """EGG"""
    click.secho(ARC_LOGO, fg='cyan')


@arc.command()
def setup():
    """Configure or Update AWS credentials"""
    click.echo("Checking for existing credentials...")

    # יצירת מופע ללא פרמטרים
    manager = AWSClient()

    # בדיקת חיבור קיים
    is_ok, info = manager.validate_connection()

    if is_ok:
        click.secho(f" Already connected as: {info}", fg='green')
        if not click.confirm("Do you want to reconnect with different credentials?"):
            click.echo(f"Your keys are managed in: {click.style(str(manager.KEYS_DIR), fg='cyan')}")
            return

    click.echo("\n--- Reconnecting to AWS ---")
    access_key = click.prompt("Enter AWS Access Key")
    secret_key = click.prompt("Enter AWS Secret Key", hide_input=True)
    region = click.prompt("Enter preferred region", default="us-east-1")
    manager.save_config(access_key, secret_key, region)
    is_ok_new, result = manager.validate_connection()

    if is_ok_new:
        click.secho("Connected and saved successfully!", fg='green', bold=True)
        click.echo(f"Key folder: {click.style(str(manager.KEYS_DIR), fg='cyan')}")
    else:
        click.secho(f"Failed to connect with new credentials: {result}", fg='red')
        # כאן אפשר להוסיף לוגיקה למחיקת הקובץ אם החיבור נכשל, אבל לרוב עדיף להשאיר כדי שהמשתמש יתקן


@arc.command()
def profile():
    """Show current identity"""
    manager = AWSClient()
    is_ok, info = manager.validate_connection()
    if is_ok:
        click.secho(f"Current Identity: {info}", fg='cyan')
    else:
        click.secho(f"Not connected: {info}", fg='red')


@arc.group()
def list():
    """List ARC resources"""
    pass


@list.command(name="s3")
def list_s3():
    with console.status("Fetching ARC-managed buckets...", spinner="line"):
        manager = AWSClient()
        buckets = manager.get_arc_buckets()
    if not buckets:
        click.secho("No ARC buckets found.", fg="yellow")
        return
    click.secho("     -----ARC-buckets-----", fg="bright_blue")
    for bucket in buckets:
        click.echo(f" • {bucket} [Managed by ARC]")


@list.command(name="ec2")
def list_ec2():
    """List ARC instances with perfectly aligned columns"""
    with console.status("Fetching ARC-managed instances...", spinner="line"):
        manager = AWSClient()
        instances = manager.get_arc_instances()

    if not instances:
        click.echo("No ARC-managed instances found.")
        return

    # כותרת טבלה - מיושרת למרכז
    click.echo("")
    click.secho(f"{'-----ARC-instances-----':^80}", fg="bright_blue", bold=True)

    # הגדרת רוחב עמודות קבוע (ללא תווי צבע)
    w_name, w_status, w_pub, w_priv, w_id = 15, 10, 15, 15, 20

    header = f"{'NAME':<{w_name}} | {'STATUS':<{w_status}} | {'PUBLIC IP':<{w_pub}} | {'PRIVATE IP':<{w_priv}} | {'ID':<{w_id}}"
    click.secho(header, bold=True, underline=True)

    for ins in instances:
        # 1. חילוץ נתונים גולמיים
        name = ins['name']
        status = ins['status']
        pub_ip = ins['public_ip']
        priv_ip = ins['private_ip']
        inst_id = ins['id']

        # 2. בניית שורה מיושרת על טקסט נקי בלבד (Plain Text)
        # שים לב: אנחנו משתמשים במשתני ה-width שהגדרנו למעלה
        line = f"{name:<{w_name}} | {status:<{w_status}} | {pub_ip:<{w_pub}} | {priv_ip:<{w_priv}} | {inst_id:<{w_id}}"

        # 3. הזרקת צבע לסטטוס
        status_color = 'green' if status == 'running' else 'yellow' if status == 'stopped' else 'white'
        colored_status = click.style(status, fg=status_color)
        # מחליף רק את המופע הראשון של הסטטוס בגרסה הצבועה שלו
        line = line.replace(status, colored_status, 1)

        # 4. הזרקת צבע ל-IP ציבורי
        if pub_ip != 'N/A':
            colored_pub_ip = click.style(pub_ip, fg='cyan')
            line = line.replace(pub_ip, colored_pub_ip, 1)

        click.echo(line)


@list.command(name="zones")
def list_zones():
    """List only ARC-managed Hosted Zones (Compact View)"""
    manager = AWSClient()

    with console.status("Fetching ARC-managed DNS zones...", spinner="line"):
        zones = manager.list_hosted_zones()

    if not zones:
        click.secho("No ARC-managed hosted zones found.", fg="yellow")
        return

    # כותרת ראשית (התאמתי את המרכוז לרוחב החדש)
    click.echo("")
    click.secho(f"{'-----ARC-DNS-Zones-----':^60}", fg="bright_blue", bold=True)

    # כותרות העמודות - צמצמנו את הרוחב כאן
    # <25 אומר: תפוס 25 תווים ותיישר לשמאל
    click.secho(f"{'DOMAIN NAME':<25} | {'ZONE ID':<22} | {'RECORDS':<8}", bold=True, underline=True)

    # השורות עצמן
    for z in zones:
        clean_name = z['name'].rstrip('.')

        # שימוש באותם רוחבים בדיוק כדי שהקו המפריד יהיה ישר
        line = f"{clean_name:<25} | {z['id']:<22} | {str(z['records']):<8}"
        click.echo(line)

@arc.group()
def create():
    """Create ARC resources"""
    pass


@create.command(name="s3")
@click.argument('name')
@click.option('--public', is_flag=True, help="Make the bucket public")
def create_s3(name, public):
    """Create a new S3 bucket with security confirmation"""
    if public:
        click.secho("WARNING: You are about to create a PUBLIC bucket.", fg='yellow')
        click.secho("This means anyone on the internet can potentially see your files.", fg='yellow')
        if not click.confirm("Are you sure you want to proceed?"):
            click.echo("Operation aborted. Your security is important")
            return
    with console.status(f"Creating bucket '{name}'...", spinner="line"):
        manager = AWSClient()
        success, message = manager.create_bucket(name, is_public=public)
    if success:
        click.secho(f"{message}", fg='green', bold=True)
    else:
        click.secho(f"Error: {message}", fg='red')


from rich.table import Table


@create.command(name="ec2")
@click.argument('name')
def create_ec2(name):
    """Launch a new EC2 instance with Key selection"""
    manager = AWSClient()

    available_keys = manager.get_available_local_keys()
    selected_key = None

    if not available_keys:
        console.print("[yellow]No local keys found. You must create one.[/yellow]")
        choice = "0"
    else:
        click.echo("Choose key pair:")
        table = Table(
            box=box.MINIMAL,
            show_header=True,
            header_style="bold cyan",
            show_lines=False  # משאיר את הטבלה נקייה בפנים
        )

        # שים לב: הורדתי את ה-width כדי שזה יהיה מהודק כמו בציור שלך
        table.add_column("ID", justify="center", style="dim", width=4)
        table.add_column("KEY NAME", style="bold white")

        # שורה 0 - יצירה חדשה
        table.add_row("0", "[yellow]Create NEW Key[/yellow]")

        # מילוי המפתחות הקיימים
        for idx, key in enumerate(available_keys, 1):
            table.add_row(str(idx), key)

        console.print(table)
        choice = click.prompt("Enter Choice ID", type=str)

    # ביצוע הבחירה בפועל
    if choice == "0":
        # --- יצירת מפתח חדש ---
        new_key_name = click.prompt("Enter new key name")
        with console.status(f"Creating key '{new_key_name}'...", spinner="line"):
            success, result = manager.create_new_key_pair(new_key_name)

        if success:
            console.print(f"[bold green]✅ Key created and saved to:[/bold green] {result}")
            selected_key = new_key_name
        else:
            console.print(f"[bold red]❌ Failed to create key:[/bold red] {result}")
            return  # עוצר את הריצה אם נכשל

    else:
        # --- בחירת מפתח קיים ---
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(available_keys):
                selected_key = available_keys[idx]
                console.print(f"Selected key: [bold green]{selected_key}[/bold green]")
            else:
                console.print("[bold red]❌ Invalid selection![/bold red]")
                return
        except ValueError:
            console.print("[bold red]❌ Invalid input! Please enter a number.[/bold red]")
            return

    os_choice = click.prompt("OS", type=click.Choice(['AL2023', 'UBUNTU'], case_sensitive=False))
    size_choice = click.prompt("Size", type=click.Choice(['t3.micro', 't3.small'], case_sensitive=False))

    user_data = None
    if click.confirm("Add User Data script?"):
        click.echo("Enter script (type 'END' on new line to finish):")
        lines = []
        while True:
            line = input()
            if line.strip().upper() == 'END': break
            lines.append(line)
        user_data = "\n".join(lines)

    if click.confirm(f"Launch server '{name}'?"):
        with console.status("lunching instance...", spinner="line"):
            success, message = manager.create_instance(
                instance_name=name,
                os_type=os_choice,
                instance_type=size_choice,
                key_name=selected_key,
                user_data=user_data
            )

        if success:
            click.secho(f"\n{message}", fg='green', bold=True)
        else:
            click.secho(f"\nError: {message}", fg='red', bold=True)
    else:
        console.print("[yellow]Operation cancelled.[/yellow]")


@create.command(name="zone")
@click.argument('domain_name')
def create_zone(domain_name):
    """Create a new Public Hosted Zone"""
    with console.status(f"Creating Hosted Zone for {click.style(domain_name, fg='cyan')}..."):
        manager = AWSClient()
        success, result = manager.create_hosted_zone(domain_name)

    if success:
        click.secho(f" Successfully created zone: {result['name']}", fg='green', bold=True)
        click.echo("\nAssign these Name Servers to your domain registrar:")
        for ns in result['name_servers']:
            click.secho(f" • {ns}", fg='bright_blue')
    else:
        click.secho(f" Error: {result}", fg='red')


@create.command(name="record")
@click.argument('zone_name')
def create_record(zone_name):
    """Add a new DNS record (A-Record)"""

    console.print(f"[bold blue]Add Record to:[/bold blue] {zone_name}")

    # שאלות פשוטות
    name = click.prompt(" Name (e.g. 'www' or '@')", default="www")
    ip = click.prompt("🔗 IP Address")

    manager = AWSClient()

    with console.status("Creating record...", spinner="line"):
        # שולחים UPSERT
        success, msg = manager.manage_dns_record(zone_name, 'UPSERT', name, ip)

    if success:
        console.print(f"[bold green] {msg}")
    else:
        console.print(f"[bold red] {msg}")

@arc.group()
def delete():
    """Delete resources"""
    pass


@delete.command(name="s3")
@click.argument('name')
def delete_s3(name):
    """Delete an ARC-managed S3 bucket"""
    if not click.confirm(click.style(f"Are you SURE you want to delete '{name}'? This cannot be undone.", fg="yellow")):
        click.echo("Delete aborted.")
        return
    with console.status("deleting bucket...", spinner="line"):
        manager = AWSClient()
        success, message = manager.delete_bucket(name)
    if success:
        click.secho(f"{message}", fg='green', bold=True)
    else:
        click.secho(f"Error: {message}", fg='red')


@delete.command(name="ec2")
@click.argument('name_or_id')
def delete_ec2(name_or_id):
    """Terminate an ARC-managed EC2 instance"""
    manager = AWSClient()

    # אזהרה ואישור
    click.secho(f"WARNING: You are about to TERMINATE instance '{name_or_id}'.", fg='yellow')
    click.secho("This action is irreversible and all unsaved data will be lost.", fg='yellow')

    if not click.confirm("Are you absolutely sure?"):
        click.echo("Termination aborted.")
        return

    with console.status("Sending termination request......", spinner="line"):
        success, message = manager.terminate_instance(name_or_id)

    if success:
        click.secho(f"{message}", fg='green', bold=True)
    else:
        click.secho(f" Error: {message}", fg='red')


@delete.command(name="zone")
@click.argument('domain_name')
def delete_zone(domain_name):
    """Delete an ARC-managed Hosted Zone by NAME"""

    if not click.confirm(click.style(f"WARNING: Are you sure you want to delete the zone '{domain_name}'?", fg="yellow")):
        click.echo("Operation cancelled.")
        return

    manager = AWSClient()

    with console.status(f"Deleting zone {domain_name}...", spinner="line"):
        success, message = manager.delete_hosted_zone(domain_name)

    if success:
        console.print(f"[bold green] {message}")
    else:
        console.print(f"[bold red] {message}")


@delete.command(name="record")
@click.argument('zone_name')
def delete_record(zone_name):
    """Delete an existing DNS record"""

    console.print(f"[yellow]Delete Record from:[/yellow] {zone_name}")
    name = click.prompt(" Name to delete (e.g. 'www')", default="www")
    ip = click.prompt(" The existing IP value (must match)")

    if click.confirm(f"Delete {name}.{zone_name} -> {ip}?"):
        manager = AWSClient()

        with console.status("[red]Deleting record...", spinner="line"):
            success, msg = manager.manage_dns_record(zone_name, 'DELETE', name, ip)

        if success:
            console.print(f"[bold green]✅ {msg}")
        else:
            console.print(f"[bold red]❌ {msg}")


@arc.group(name="stop")
def stop_group():
    """Stop ARC resources (ec2, etc.)"""
    pass


@stop_group.command(name="ec2")
@click.argument('name')
def stop_ec2(name):
    """Stop a running ARC instance"""
    manager = AWSClient()
    click.echo(f"Stopping instance '{name}'...")
    success, message = manager.manage_instance(name, 'stop')
    click.secho(message, fg='green' if success else 'red')


# --- פקודת START ---
@arc.group(name="start")
def start_group():
    """Start ARC resources (ec2, etc.)"""
    pass


@start_group.command(name="ec2")
@click.argument('name')
def start_ec2(name):
    """Start a stopped ARC instance"""
    manager = AWSClient()
    click.echo(f"Starting instance '{name}'...")
    success, message = manager.manage_instance(name, 'start')
    click.secho(message, fg='green' if success else 'red')


@arc.group()
def upload():
    """Upload files to S3"""
    pass


@upload.command(name="s3")
@click.argument('file_path', type=click.Path(exists=True))
@click.argument('bucket_name')
def upload_s3(file_path, bucket_name):
    click.secho(f"uploading file to {bucket_name}...")
    manager = AWSClient()
    success, message = manager.upload_to_s3(file_path, bucket_name)
    click.secho(message, fg='green' if success else 'red')


if __name__ == '__main__':
    arc()