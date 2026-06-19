# Ansible Operations

Ansible is the main administration tool for the Raspberry Pis. The playbooks live in `modules/administration/lab-ansible` in this repository. The same playbooks live on the management PC at `~/lab-ansible`.

The WSL controller is the preferred execution place. The WSL controller has the SSH key that reaches the managed Pis. Local execution from the Mac did not authenticate to the Pis during inspection.

## Files

| File | Purpose |
| --- | --- |
| `hosts.bootstrap.ini` | First time access with the bootstrap user |
| `hosts.admin.ini` | Normal access with the admin user and SSH key |
| `hosts.ini` | Guest oriented inventory from earlier setup |
| `bootstrap_python.yml` | Python bootstrap for minimal AlmaLinux images |
| `streamline.yml` | Main provisioning playbook |
| `cleanup.yml` | Non admin user cleanup |

## Provisioning Flow

First bootstrap Python on a new Pi. The bootstrap inventory is used for this one time step. The command should run from the WSL controller.

```bash
cd ~/lab-ansible
ansible-playbook -i hosts.bootstrap.ini bootstrap_python.yml
```

Next run the main provisioning playbook. The bootstrap inventory can be used for first provisioning. The admin inventory should be used after the admin key has been installed.

```bash
cd ~/lab-ansible
ansible-playbook -i hosts.admin.ini streamline.yml
```

Finally verify the node. The verification should check SSH, sudo, Mosquitto, and Cockpit. The verification should also check the expected host name.

```bash
cd ~/lab-ansible
ansible -i hosts.admin.ini raspis -m ping
ansible -i hosts.admin.ini raspis -m shell -a 'hostname; systemctl is-active mosquitto cockpit.socket'
```

## Provisioned State

The main playbook creates an `admin` user. The playbook locks password login for that user. The playbook installs the controller public key. The playbook allows passwordless sudo for `admin`.

The main playbook installs Cockpit, Python, pip, Mosquitto, and `paho-mqtt`. The playbook enables Cockpit. The playbook configures Mosquitto on `0.0.0.0:1883`. The playbook allows anonymous MQTT access.

The main playbook removes non system users after admin access works. This action is powerful. The inventory should be correct before the cleanup stage runs.

## Current Drift

The live reachable Pis contain services beyond the playbook. Docker, MySQL, HTTP sockets, and XRDP were observed. These services are not all defined in `streamline.yml`. Therefore service ownership should be documented or folded into Ansible.

The active inventory manages only four Pis. The source DNAT table documents more devices. Therefore the inventory should be reconciled with the intended device list.

