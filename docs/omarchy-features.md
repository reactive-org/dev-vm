# Select developer features

With the chosen guest already running and managed SSH ready:

```bash
make apply-playbook VM_NAME="Dev Omarchy" \
  OMARCHY_FEATURES=workstation,browsers,docker,languages,agents,credentials
```

Select only what you need. The default is `workstation`; omitted features leave
existing software and settings alone. An existing browser/runtime/application is
reused on the official image. A lean image receives the prerequisites for the
selected feature through native Omarchy commands and mise.

| Feature / Ansible tag | Default selection when enabled |
| --- | --- |
| `workstation` | Foot size 16, host-owned idle policy and the GPU compatibility repair |
| `browsers` | Chromium; Firefox can also be selected |
| `docker` | Docker, Buildx, Compose, native UFW integration and socket activation |
| `languages` | Node using Omarchy's configured mise version |
| `agents` | Claude CLI using Omarchy's configured mise version |
| `credentials` | 1Password app and CLI, without signing in or copying credentials |

Copy [the example configuration](../omarchy/examples/features.yml) into the ignored
`omarchy/local/features.yml`, edit its selections, and pass it explicitly:

```bash
make apply-playbook VM_NAME="Dev Omarchy" OMARCHY_FEATURES=languages,agents \
  OMARCHY_VARS_FILE="$PWD/omarchy/local/features.yml"
```

Values configure a feature; they do not enable it. Each role has its own Ansible
tag. Empty lists/maps select no tools for that feature. An empty mise version
uses Omarchy's existing declaration; a string such as `"3"`, `"lts"` or an exact
version creates/selects a user-level mise setting without replacing other tools.
System Python remains `/usr/bin/python3` for Ansible.

Preview the manager connection/proposal, or inspect planned changes:

```bash
make apply-playbook VM_NAME="Dev Omarchy" OMARCHY_FEATURES=docker OMARCHY_PLAYBOOK_PLAN=yes
make apply-playbook VM_NAME="Dev Omarchy" OMARCHY_FEATURES=browsers,languages OMARCHY_PLAYBOOK_CHECK=yes
```

Check mode stages and removes a temporary payload but does not install packages,
write workstation preferences, start services or enable a sudo grant. Workstation
and Docker firewall predictions are conservative when they cannot be evaluated
without applying native tools. Normal privileged runs use Omarchy's interactive
60-minute sudo grant and revoke it on completion, failure or interruption.

The launcher generates a private temporary inventory from VM Manager's pinned
SSH command. It never creates, starts, resizes or reboots a VM. Docker retains
Omarchy's normal sudo/polkit access policy; no docker-group membership is added.
Use VM Manager for a new login/restart when needed, then validate hardware and
integration with `make check-omarchy-vm`.

See [the playbook contract](omarchy-playbooks.md) for selection, image
compatibility and validation limits. Existing ignored `local-vars.yml` and
`developer_extra_tasks.yml` files are no longer loaded; personal files are left
in place and are not copied into a guest.
