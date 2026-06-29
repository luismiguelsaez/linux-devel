## Packages

```bash
pacman -S brave-bin mangohud cmake cuda proton-cachyos-native steam cachyos-gaming-meta heroic-games-launcher-bin
```

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

- **Rollback to initial status**

If you need to undo the hibernation fix and restore the original zram setup:

1. Remove the swap file and disable it:

```bash
sudo swapoff /swapfile
sudo rm /swapfile
```

2. Remove the swap entry from `/etc/fstab` — delete this line:

```
/swapfile none swap defaults 0 0
```

3. Remove `resume` from the HOOKS line in `/etc/mkinitcpio.conf`:

```bash
sudo sed -i 's/ resume$//' /etc/mkinitcpio.conf
```

4. Remove `resume=UUID=...` from `/etc/default/grub`:

```bash
sudo sed -i "s| resume=UUID=.*||" /etc/default/grub
```

5. Rebuild GRUB and initramfs:

```bash
sudo grub-mkconfig -o /boot/grub/grub.cfg
sudo mkinitcpio -P
```

6. Unmask and re-enable the zram service:

```bash
sudo systemctl unmask systemd-zram-setup@zram0.service
sudo systemctl enable --now systemd-zram-setup@zram0.service
```

7. Reboot. The system will be back to using zram for swap.
