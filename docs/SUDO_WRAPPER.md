# Constrained sudo wrapper for Gate host mounts

Date: 2025-12-29

This optional wrapper lets you run the specific host-side NFS mount/unmount commands
used by Gate without repeated password prompts, while keeping the scope tightly
restricted. It only allows `mount -t nfs4 ...` and `umount` for paths you explicitly
allow in a root-owned config file.

## What it does (and does not) allow
- Allowed: NFSv4 mounts that match your allowlist (remote, port, mount prefix).
- Allowed: `umount` of paths under your allowlisted prefixes.
- Not allowed: any other commands, mount types, or options.

## Install the wrapper
```
sudo install -m 0755 ./scripts/sudo_allow.py /usr/local/bin/sudo-allow
```

## Configure the allowlist
1) Create the config directory and seed file:
```
sudo mkdir -p /etc/sudo-allow
sudo install -m 0644 ./scripts/sudo_allowlist.sample.json /etc/sudo-allow/allowlist.json
```

2) Edit `/etc/sudo-allow/allowlist.json` to match your setup:
- Replace `YOUR_USER` with your actual username.
- Add any additional NFS remotes you plan to mount (e.g., Firecracker guest IPs).
- Keep the mount prefixes as narrow as possible.

Example:
```
{
  "allowed_remotes": ["127.0.0.1:/mnt/gate"],
  "allowed_nfs_ports": [2049],
  "allowed_mount_prefixes": ["/home/your_user/.local/state/gate/mounts"],
  "allowed_umount_prefixes": ["/home/your_user/.local/state/gate/mounts"]
}
```

## Add a sudoers entry (NOPASSWD for the wrapper only)
Edit a dedicated sudoers drop-in:
```
sudo visudo -f /etc/sudoers.d/sudo-allow
```

Add a single line (replace `your_user` as needed):
```
your_user ALL=(root) NOPASSWD: /usr/local/bin/sudo-allow
```

## Use it with Gate
Set the command prefix Gate should use when it needs sudo for host mounts:
```
export GATE_SUDO_CMD="sudo /usr/local/bin/sudo-allow"
```

Now `gate up` and `gate host-mount` can mount/unmount NFS without prompting,
as long as the mount matches the allowlist.

Optional: override the allowlist path:
```
export SUDO_ALLOWLIST_PATH=/etc/sudo-allow/allowlist.json
```

## Troubleshooting
- If you see “remote not in allowlist”, update `/etc/sudo-allow/allowlist.json`.
- If you see “path not under an allowed prefix”, adjust the allowed mount prefixes.
- If it says the allowlist is writable by group/other, fix permissions:
  `sudo chmod 0644 /etc/sudo-allow/allowlist.json`.
