# Remindotron

Save reminders and notify about them every day

```
usage: Remindotron [-h] [--version] [--database /path/to/db] [--debug]
                   {insert,show,run,install,uninstall} ...

positional arguments:
  {insert,show,run,install,uninstall}
    insert              Insert new item in database
    show                Show all database items
    run                 Run the cronjob
    install             Install systemd unit files
    uninstall           Remove systemd unit files

options:
  -h, --help            show this help message and exit
  --version             show version
  --database /path/to/db
                        path to database to use [default: ./remindotron.db]
  --debug               show debug information
  ```
