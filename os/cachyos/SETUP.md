## Hibernation not working

- [Arch document](https://wiki.archlinux.org/title/Power_management#ACPI_events)

Edit /etc/systemd/logind.conf

HandleLidSwitch=suspend
HandleLidSwitchDocked=suspend
