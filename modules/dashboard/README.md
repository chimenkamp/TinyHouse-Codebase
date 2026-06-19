# TinyHouse Dashboard

The TinyHouse dashboard provides a small web view for operations. The dashboard shows the known private IP addresses. The dashboard opens a browser shell. The dashboard streams MQTT messages. The dashboard can proxy a configured camera feed.

## Installation

The dashboard uses Python packages only. The Management PC should install the dependencies inside a virtual environment.

```bash
cd modules/dashboard
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

On Windows PowerShell the activation command is different.

```powershell
cd modules\dashboard
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Local Mode

Local mode is for the Management PC. Local mode scans `192.168.1.0/24` directly. Local mode connects to the local MQTT broker. Local mode opens a local shell from the main shell button. Online device cards show a shell button when port `22` is open.

```bash
python run_dashboard_local.py
```

The browser should open this address.

```text
http://127.0.0.1:8088/
```

## Tunnel Mode

Tunnel mode is for a computer outside the TinyHouse network. Tunnel mode uses the SSH settings from `config.yaml`. Tunnel mode runs status checks on the Management PC. Tunnel mode opens the Management PC shell from the main shell button. Online device cards show a shell button when a public SSH route is open. Tunnel mode starts `mosquitto_sub` on the Management PC.

```bash
python run_dashboard_tunnel.py
```

The browser should open this address.

```text
http://127.0.0.1:8088/
```

The header shows the tunnel state. `SSH connected` means the dashboard reached the Management PC. `SSH failed` means the target cards are not a TinyHouse network result yet. In that case the status panel shows the SSH error.

The health endpoint can be checked directly.

```bash
curl http://127.0.0.1:8088/api/health
```

The dashboard uses `ssh_command` as the SSH alias source. For example `ssh tinyhouse` makes the dashboard look up `tinyhouse` in the user's SSH config. The dashboard also uses `IdentityFile` from the SSH config. The dashboard passes the configured password to Paramiko as a password and as a possible key passphrase. A name resolution error means the alias or host could not be resolved before authentication started. A `publickey` error means the server rejected password login and the configured key did not authenticate.

The default tunnel backend is `openssh`. This backend runs the real `ssh tinyhouse` command in a PTY. The backend sends the configured password when the nested Management PC login asks for it. If the header says `SSH connected` but all private IP targets are offline, then the Management PC is reachable but it currently has no route to the TinyHouse private subnet.

The run scripts use constants at the top of each file. The run scripts do not use CLI arguments. The run scripts automatically restart themselves with the dashboard virtual environment.

The dashboard can be stopped with this helper.

```bash
python kill_dashboard.py
```

## Port Forward Mode

Port forward mode is another outside option. First run the dashboard on the Management PC with local mode. Next create an SSH tunnel from the outside computer.

```bash
ssh -L 8088:127.0.0.1:8088 tinyhouse
```

The outside browser can then open the local forwarded address.

```text
http://127.0.0.1:8088/
```

## Configuration

The file `config.yaml` contains the operational defaults. The file contains the Management PC SSH command. The file contains the Management PC password. The dashboard API redacts that password before it sends configuration data to the browser.

The camera section controls the camera proxy. The dashboard writes camera form changes back to `config.yaml`. The camera path should match the device feed endpoint. For example some cameras use `/video` or `/mjpeg`.

The configured TinyHouse camera uses `132.180.196.165` with user `admin`. The dashboard uses direct camera access for that public address. Port `80` should use `scheme: http`; the dashboard will follow a camera redirect to HTTPS when the device provides one. A direct `https` URL on port `80` often fails with `SSL: WRONG_VERSION_NUMBER` because the camera is answering with plain HTTP. Use `scheme: https` with the camera's HTTPS port, usually `443`.

When `camera.access_mode` is set to `tunnel`, tunnel mode opens an OpenSSH local forward through the Management PC before requesting the feed. This supports both HTTP and HTTPS camera endpoints through the VPS path when `management_pc.connection_backend` is `openssh`.

Some camera web UIs load CSS and JavaScript from `/api/web-static/...` after the feed page opens. The dashboard proxies those paths back to the configured camera so the server log does not fill with camera asset 404s.

The network cards show private and public checks separately. Private checks target `192.168.1.x` from the Management PC. Public checks target the DNAT ports on `132.180.196.167` from the dashboard host. Therefore a device can be reachable through a public port while its private check is unavailable.

The shell section controls browser shell access. The main shell button opens the Management PC shell in tunnel mode. Device cards with shell access show two shell actions. `WEB` opens the browser shell. `PC` asks the local backend to open the same target in a native terminal on the operator machine. Target shell commands use `shell_identity_file` when that value is present. Target shells disable password and keyboard-interactive authentication by default. A target can override these values with `shell_command`, `shell_identity_file`, `shell_password_authentication`, and `shell_keyboard_interactive_authentication` in `config.yaml`.

Target MQTT actions are configured per device. A target with `mqtt_capable: true`, `mqtt_host`, `mqtt_port`, and `mqtt_topics` gets an `MQ` button on its network card. The Scale target subscribes directly to `broker.emqx.io:1883` with `tinyhouse/scale/#`. If the ESP firmware publishes to a different topic, change `targets[].mqtt_topics` in `config.yaml`.

## Documentation Link

The dashboard links to the documentation URL from `server.docs_url`. The default value expects the VitePress documentation to run on port `5173`.

## Security Note

The dashboard provides shell access. The dashboard should bind to `127.0.0.1` unless the surrounding network is trusted. SSH port forwarding should expose the dashboard only to the operator machine.
