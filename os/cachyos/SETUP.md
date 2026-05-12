## Hibernation not working

- [Arch document](https://wiki.archlinux.org/title/Power_management#ACPI_events)

Edit /etc/systemd/logind.conf

HandleLidSwitch=suspend
HandleLidSwitchDocked=suspend

## Disable SWAP

- Disable `zram` swap service

```bash
systemctl stop systemd-zram-setup@zram0.service
systemctl mask systemd-zram-setup@zram0.service
```

- Create swap file

```bash
sudo mkswap -U clear --size 4G --file /swapfile
```

- Modify fstab

```
/swapfile none swap defaults 0 0
```

