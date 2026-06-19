# Access

The access model uses a gateway path. A client connects to the VPS. The VPS forwards the session into the Windows management PC. The Windows management PC runs WSL for Linux administration.

![TinyHouse access model](/diagrams/access-model.svg)

## Management PC Access

The local SSH alias is `tinyhouse`. The alias points to the VPS address `46.224.118.171`. The alias uses user `christian` and the key file `~/.ssh/christian_tinyhouse`.

```bash
ssh tinyhouse
```

The login currently lands in a Windows command shell. From that shell, WSL commands can be started with `wsl.exe`. The Ansible controller files live inside WSL.

```cmd
wsl.exe -e sh -lc "cd ~/lab-ansible && ansible -i hosts.admin.ini raspis -m ping"
```

## Raspberry Pi Access

The preferred Raspberry Pi access path is Ansible from WSL. The inventory uses the public router address and DNAT ports. The admin key lives in the WSL user home.

```bash
cd ~/lab-ansible
ansible -i hosts.admin.ini raspis -m ping
```

Direct SSH follows the same DNAT model. The command below shows the pattern. The exact port comes from the inventory.

```bash
ssh -p 4024 admin@132.180.196.167
```

## Credential Handling

The rendered documentation does not publish operational passwords. Older working notes may still contain credentials outside the rendered site. Secrets should move to a password manager or an encrypted secret file before this repository becomes shared.

The Ansible inventories currently contain bootstrap credentials. Those values should be removed or encrypted with Ansible Vault. The rendered pages use placeholders when a command would otherwise expose a secret.

## Remote Users

The source documentation describes per user access through the VPS. A user authenticates to the VPS with a public key. The VPS can force the user into the Windows reverse tunnel. The user does not receive a normal VPS shell.

The source documentation also describes a tunnel user. The tunnel user maintains the reverse SSH tunnel from Windows to the VPS. The tunnel user should not be used interactively.
