# inwx-nameserver-robot

🤖 Automatically updates INWX AAAA DNS records with the current global IPv6 address of a network interface. Runs as a systemd timer every 2 minutes.

## Requirements

- Python 3
- `requests` library (installed automatically by `install.sh`)
- A network interface with a public global IPv6 address
- An [INWX](https://www.inwx.com) account with API access

## Installation

```bash
sudo ./install.sh
```

An optional installation path can be passed as the first argument (default: `/opt/inwx-nameserver-robot`):

```bash
sudo ./install.sh /srv/inwx-nameserver-robot
```

The script will:

1. Create the system user `inwx-nameserver-robot`
2. Prompt for credentials and DNS configuration, then write `config.py`
3. Deploy `main.py` and `config.py` to the installation directory
4. Create a Python virtual environment and install dependencies
5. Install and enable the systemd timer

## Configuration

| Variable | Description |
|---|---|
| `INWX_USERNAME` | INWX account username |
| `INWX_PASSWORD` | INWX account password |
| `DOMAIN` | Domain to update (e.g. `example.com`) |
| `RECORD_NAMES` | List of record names to update (`""` = root `@`) |
| `INTERFACE` | Network interface to read the IPv6 address from |
| `INWX_API_URL` | INWX JSON-RPC API endpoint |
| `CACHE_FILE` | Path to cache file for last known IPv6 address |

## Usage

Check timer status:

```bash
systemctl status inwx-nameserver-robot.timer
```

View logs:

```bash
journalctl -u inwx-nameserver-robot.service
```

Run manually:

```bash
systemctl start inwx-nameserver-robot.service
```
