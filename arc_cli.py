import click
from services import AWSClient
from rich.console import Console
from rich import box
import sys
import os
from rich.table import Table

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

    manager = AWSClient()
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
    """List only ARC-managed instances"""
    with console.status("Fetching ARC-managed instances...", spinner="line"):
        manager = AWSClient()
        instances = manager.get_arc_instances()

    if not instances:
        click.echo("No ARC-managed instances found.")
        return

    click.echo("")
    click.secho(f"{'-----ARC-instances-----':^80}", fg="bright_blue", bold=True)
    w_name, w_status, w_pub, w_priv, w_id = 15, 10, 15, 15, 20
    header = f"{'NAME':<{w_name}} | {'STATUS':<{w_status}} | {'PUBLIC IP':<{w_pub}} | {'PRIVATE IP':<{w_priv}} | {'ID':<{w_id}}"
    click.secho(header, bold=True, underline=True)

    for ins in instances:
        name = ins['name']
        status = ins['status']
        pub_ip = ins['public_ip']
        priv_ip = ins['private_ip']
        inst_id = ins['id']

        line = f"{name:<{w_name}} | {status:<{w_status}} | {pub_ip:<{w_pub}} | {priv_ip:<{w_priv}} | {inst_id:<{w_id}}"
        status_color = 'green' if status == 'running' else 'yellow' if status == 'stopped' else 'white'
        colored_status = click.style(status, fg=status_color)
        line = line.replace(status, colored_status, 1)

        if pub_ip != 'N/A':
            colored_pub_ip = click.style(pub_ip, fg='cyan')
            line = line.replace(pub_ip, colored_pub_ip, 1)
        click.echo(line)


@list.command(name="zones")
def list_zones():
    """List only ARC-managed Hosted Zones"""
    manager = AWSClient()
    with console.status("Fetching ARC-managed DNS zones...", spinner="line"):
        zones = manager.list_hosted_zones()

    if not zones:
        click.secho("No ARC-managed hosted zones found.", fg="yellow")
        return

    click.echo("")
    click.secho(f"{'-----ARC-DNS-Zones-----':^60}", fg="bright_blue", bold=True)
    click.secho(f"{'DOMAIN NAME':<25} | {'ZONE ID':<22} | {'RECORDS':<8}", bold=True, underline=True)

    for z in zones:
        clean_name = z['name'].rstrip('.')
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
    """Create a new S3 bucket"""
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


@create.command(name="ec2")
@click.argument('name')
def create_ec2(name):
    """Launch a new EC2 instance"""
    manager = AWSClient()
    with console.status("Checking user quota...", spinner="line"):
        can_create, msg = manager.check_quota_status()

    if not can_create:
        console.print(f"[bold red]{msg}[/bold red]")
        return

    available_keys = manager.get_available_local_keys()
    selected_key = None

    if not available_keys:
        click.secho(f"No local keys found. You must create one.", fg='yellow', bold=True)
        choice = "0"
    else:
        click.echo("Choose key pair:")
        table = Table(
            box=box.MINIMAL,
            show_header=True,
            header_style="bold cyan",
            show_lines=False
        )

        table.add_column("ID", justify="center", style="dim", width=4)
        table.add_column("KEY NAME", style="bold white")
        table.add_row("0", "[yellow]Create NEW Key[/yellow]")
        for idx, key in enumerate(available_keys, 1):
            table.add_row(str(idx), key)
        console.print(table)
        choice = click.prompt("Enter Choice ID", type=str)

    if choice == "0":
        new_key_name = click.prompt("Enter new key name")
        with console.status(f"Creating key '{new_key_name}'...", spinner="line"):
            success, result = manager.create_new_key_pair(new_key_name)

        if success:
            console.print(f"[bold green]✅ Key created and saved to:[/bold green] {result}")
            selected_key = new_key_name
        else:
            console.print(f"[bold red]❌ Failed to create key:[/bold red] {result}")
            return

    else:
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
    click.echo(f"Add Record to: {zone_name}")
    name = click.prompt(" Name (e.g. 'www' or '@')", default="www")
    ip = click.prompt("🔗 IP Address")
    with console.status("Creating record...", spinner="line"):
        manager = AWSClient()
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
@click.argument('name', required=False)
@click.option('--all', is_flag=True, help="Delete ALL ARC-managed buckets")
def delete_s3(name, all):
    """Delete a specific bucket OR all ARC buckets"""
    manager = AWSClient()
    if all:
        with console.status("Fetching ARC buckets...", spinner="line"):
            buckets = manager.get_arc_buckets()

        if not buckets:
            click.secho("No ARC buckets found.", fg="red")
            return

        # 2. אזהרה
        click.secho(f"WARNING: You are about to DELETE {len(buckets)} BUCKETS!", fg="yellow", bold=True)
        click.secho(f"Targets: {', '.join(buckets)}", fg="yellow", bold=True)

        if not click.confirm(click.style("Are you ABSOLUTELY SURE?")):
            click.secho("Operation cancelled.", fg="yellow")
            return

        results = []

        with console.status("Initializing destruction...", spinner="line") as status:
            for bucket in buckets:

                status.update(f"Deleting bucket: {bucket}...", spinner="line")

                success, msg = manager.delete_bucket(bucket, force=True)
                results.append((bucket, success, msg))


        click.secho("--- Deletion Summary ---", fg="cyan", bold=True)

        for bucket, success, msg in results:
            if success:
                click.secho(f" {bucket}: Deleted successfully", fg="green")
            else:
                click.secho(f"{bucket}: {msg}", fg="red")
        return

    if not name:
        click.secho("Error: You must specify a bucket NAME or use --all", fg="red")
        return

    if not click.confirm(click.style(f"Delete bucket '{name}'?", fg="yellow")):
        return

    with console.status(f"Deleting '{name}'...", spinner="dots"):
        success, message = manager.delete_bucket(name, force=True)

    if success:
        click.secho(f"{message}", fg='green', bold=True)
    else:
        click.secho(f"{message}", fg='red')


@delete.command(name="ec2")
@click.argument('name_or_id', required=False)
@click.option('--all', is_flag=True, help="Terminate ALL ARC-managed instances")
def delete_ec2(name_or_id, all):
    """Terminate a specific instance OR all ARC instances"""
    manager = AWSClient()

    if all:
        with console.status("Fetching ARC instances...", spinner="line"):
            instances = manager.get_arc_instances()

        if not instances:
            click.secho("No ARC instances found.", fg="red")
            return

        click.secho(f"WARNING: You are about to TERMINATE {len(instances)} SERVERS!", fg="yellow", bold=True)
        names = [i['name'] for i in instances]
        click.secho(f"Targets: {', '.join(names)}", fg="yellow")

        if not click.confirm(click.style("Are you ABSOLUTELY SURE?", fg="yellow")):
            click.secho("Operation cancelled.", fg="red")
            return

        results = []
        with console.status(f"Terminating {len(instances)} instances...") as status:
            for inst in instances:
                name = inst['name']
                inst_id = inst['id']

                status.update(f"Terminating {name} ({inst_id})...")
                success, msg = manager.terminate_instance(inst_id)
                results.append((name, success, msg))

        click.echo("")
        click.secho("--- Termination Summary ---", fg="cyan", bold=True)
        for name, success, msg in results:
            if success:
                click.secho(f"✅ {name}: Terminated successfully", fg="green")
            else:
                click.secho(f"❌ {name}: {msg}", fg="red")
        return

    if not name_or_id:
        click.secho("Error: You must specify an instance NAME/ID or use --all", fg="red")
        return

    click.secho(f"WARNING: You are about to TERMINATE instance '{name_or_id}'.", fg='yellow')
    if not click.confirm("Are you sure?"):
        return

    with console.status("Terminating...", spinner="line"):
        success, message = manager.terminate_instance(name_or_id)

    if success:
        click.secho(f"{message}", fg='green', bold=True)
    else:
        click.secho(f"{message}", fg='red')


@delete.command(name="zone")
@click.argument('domain_name', required=False)
@click.option('--all', is_flag=True, help="Delete ALL ARC-managed Hosted Zones")
def delete_zone(domain_name, all):
    """Delete a Hosted Zone (or ALL zones)"""
    manager = AWSClient()

    if all:
        with console.status("Fetching ARC zones...", spinner="line"):
            zones = manager.list_hosted_zones()

        if not zones:
            click.secho("No ARC zones found.", fg="red")
            return

        click.secho(f"WARNING: You are about to DELETE {len(zones)} DNS ZONES!", fg="yellow",)
        names = [z['name'] for z in zones]
        click.secho(f"Targets: {', '.join(names)}", fg="yellow")

        if not click.confirm(click.style("Are you ABSOLUTELY SURE?")):
            click.secho("Operation cancelled.", fg="red")
            return
        results = []
        with console.status(f"Deleting {len(zones)} zones...", spinner="line") as status:
            for z in zones:
                z_name = z['name']
                z_id = z['id']

                status.update(f"Deleting {z_name}...")
                success, msg = manager.delete_hosted_zone(z_id, force=True)
                results.append((z_name, success, msg))

        click.echo("")
        click.secho("--- Deletion Summary ---", fg="cyan", bold=True)
        for name, success, msg in results:
            if success:
                click.secho(f"{name}: Deleted successfully", fg="green")
            else:
                click.secho(f"{name}: {msg}", fg="red")
        return

    if not domain_name:
        click.secho("Error: You must specify a domain name or use --all", fg="red")
        return

    if not click.confirm(click.style(f"WARNING: Delete zone '{domain_name}'?", fg="yellow")):
        return

    with console.status(f"Deleting zone {domain_name}...", spinner="line"):
        success, message = manager.delete_hosted_zone(domain_name, force=True)

    if success:
        console.print(f"[bold green]{message}[/bold green]")
    else:
        console.print(f"[bold red]{message}[/bold red]")


@delete.command(name="record")
@click.argument('zone_name')
def delete_record(zone_name):
    """Delete an existing DNS record"""

    console.print(f"[yellow]Delete Record from:[/yellow] {zone_name}")
    name = click.prompt(" Name to delete (e.g. 'www')", default="www")
    ip = click.prompt(" The existing IP value (must match)")

    if click.confirm(f"Delete {name}.{zone_name} -> {ip}?"):
        with console.status("[red]Deleting record...", spinner="line"):
            manager = AWSClient()
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
    with console.status("Deleting record...", spinner="line"):
        manager = AWSClient()
        success, message = manager.manage_instance(name, 'stop')
    click.secho(message, fg='green' if success else 'red')


@arc.group(name="start")
def start_group():
    """Start ARC resources (ec2, etc.)"""
    pass


@start_group.command(name="ec2")
@click.argument('name')
def start_ec2(name):
    """Start a stopped ARC instance"""
    with console.status(f"Starting instance '{name}'...", spinner="line"):
        manager = AWSClient()
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
    with console.status(f"uploading file to {bucket_name}...", spinner="line"):
        manager = AWSClient()
        success, message = manager.upload_to_s3(file_path, bucket_name)
    click.secho(message, fg='green' if success else 'red')


if __name__ == '__main__':
    arc()