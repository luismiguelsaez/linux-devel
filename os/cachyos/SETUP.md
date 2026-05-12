## Hibernation not working

- [Arch document](https://wiki.archlinux.org/title/Power_management#ACPI_events)

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

- Enable `resume` in mkinitcpio.conf

```
HOOKS=(base systemd autodetect microcode kms modconf block keyboard sd-vconsole plymouth filesystems resume)
```

- Rebuild

```bash
sudo mkinitcpio -P
```

