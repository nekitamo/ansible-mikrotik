#!/usr/bin/env python
# coding: utf-8
"""MikroTik RouterOS backup and change manager"""

import os
import socket
from mikrotik_ansible import *

DOCUMENTATION = """
---

module: mikrotik_export
short_description: MikroTik RouterOS configuration export
description:
    - Exports full router configuration to <identity>_<software_id>.rsc file in export directory
    - By default no local export file is created on the router (enable with local_file:yes)
    - Create ansible user with ssh-key to avoid using username/password in playbooks
return_data:
    - identity
    - software_id
    - export_dir
    - export_file
options:
    export_dir:
        description:
            - Directory where exported file (<identity>_<software_id>.rsc) is written after export
        required: true
        default: null
    timestamp:
        description:
            - Include default timestamp in export file (first line), disabled for version tracking
        required: false
        default: false
    hide_sensitive:
        description:
            - Do not include passwords or other sensitive info in exported configuration file
        required: false
        default: true
    local_file:
        description:
            - Also write config as local file on device (ansible-export.rsc) before export
        required: false
        default: false
    verbose:
        description:
            - Export verbose config including default option values (large export file)
        required: false
        default: false
    port:
        description:
            - SSH listening port of the MikroTik device
        required: false
        default: 22
    hostname:
        description:
            - IP Address or hostname of the MikroTik device
        required: true
        default: null
    username:
        description:
            - Username used to login to the device
        required: false
        default: ansible
    password:
        description:
            - Password used to login to the device
        required: false
        default: null

"""
EXAMPLES = """
# example playbook
---

- name: Export Mikrotik RouterOS config
  hosts: mikrotik_routers
  gather_facts: false
  connection: local

  tasks:

  - name: Export router configurations
    mikrotik_export:
        hostname: "{{ inventory_hostname }}"
        export_dir: exports
        hide_sensitive: false
        timestamp: true

"""
RETURN = """
identity:
    description: Returns device identity (system identity print)
    returned: always
    type: string
software_id:
    description: Returns device software_id (system identity print)
    returned: always
    type: string
export_dir:
    description: Returns full os path for export directory
    returned: always
    type: string
export_file:
    description: Returns filename of exported configuration (<identity>_<software_id>.rsc)
    returned: always
    type: string
"""
SHELL_USAGE = """

mikrotik_export.py --shellmode --hostname=<hostname> --export_dir=<path>
               [--timestamp=yes|no] [--hide_sensitive] [--verbose] [--local_file]
               [--port=<port>] [--username=<username>] [--password=<password>]

"""

try:
    import paramiko
except ImportError as import_error:
    HAS_SSHCLIENT = False

try:
    from ansible.module_utils.basic import AnsibleModule
except ImportError:
    SHELLMODE = True

def main():
    rosdev = {}
    cmd_timeout = 15
    changed = False    
    if not SHELLMODE:
        module = AnsibleModule(
            argument_spec=dict(
                export_dir=dict(required=True, type='path'),
                timestamp=dict(default=False, type='bool'),
                hide_sensitive=dict(default=True, type='bool'),
                local_file=dict(default=False, type='bool'),
                verbose=dict(default=False, type='bool'),
                hostname=dict(required=True),
                username=dict(default='ansible', type='str'),
                password=dict(default=None, type='str'),
                port=dict(default=22, type='int'),
                timeout=dict(default=30, type='float')
            ), supports_check_mode=False
        )
        if not HAS_SSHCLIENT:
            safe_fail(module, msg='There was a problem loading module: ',
                      error=str(import_error))
        export_dir = os.path.expanduser(module.params['export_dir'])
        timestamp = module.params['timestamp']
        hide_sensitive = module.params['hide_sensitive']
        local_file = module.params['local_file']
        verbose = module.params['verbose']
        rosdev['hostname'] = socket.gethostbyname(module.params['hostname'])
        rosdev['username'] = module.params['username']
        rosdev['password'] = module.params['password']
        rosdev['port'] = module.params['port']
        rosdev['timeout'] = module.params['timeout']

    elif len(sys.argv) > 1:
        if not HAS_SSHCLIENT:
            sys.exit("SSH client error: " + str(import_error))
        if 'export_dir' not in SHELLOPTS:
            sys.exit("export_dir required, specify with --export_dir=<path>")
        export_dir = os.path.expanduser(SHELLOPTS['export_dir'])
        rosdev['hostname'] = socket.gethostbyname(SHELLOPTS['hostname'])
        rosdev['username'] = SHELLOPTS['username']
        rosdev['password'] = SHELLOPTS['password']
        rosdev['port'] = SHELLOPTS['port']
        rosdev['timeout'] = SHELLOPTS['timeout']
        hide_sensitive = True
        local_file = False
        verbose = False
        timestamp = False
        module = None
        if 'hide_sensitive' in SHELLOPTS:
            hide_sensitive = SHELLOPTS['hide_sensitive']
        if 'timestamp' in SHELLOPTS:
            timestamp = SHELLOPTS['timestamp']
        if 'local_file' in SHELLOPTS:
            local_file = SHELLOPTS['local_file']
        if 'verbose' in SHELLOPTS:
            verbose = SHELLOPTS['verbose']
    else:
        sys.exit(SHELL_USAGE)

    device = paramiko.SSHClient()
    device.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    device_connect(module, device, rosdev)

    response = sshcmd(module, device, cmd_timeout, "system identity print")
    identity = str(response.split(": ")[1])
    identity = identity.strip()
    software_id = sshcmd(module, device, cmd_timeout,
                         ":put [ /system license get software-id ]")
    export_file = identity + "-" + software_id + "-export.rsc"
    export_dir = os.path.realpath(export_dir)
    exportfull = os.path.join(export_dir, export_file)
    exportcmd = "export"
    if hide_sensitive:
        exportcmd += " hide-sensitive"
    if verbose:
        exportcmd += " verbose"
    if local_file:
        exportcmd += " file=ansible-export"
    response = sshcmd(module, device, cmd_timeout, exportcmd)
    if local_file:
        sftp = device.open_sftp()
        sftp.get("/ansible-export.rsc", exportfull)
        sftp.close()
        changed = True
    else:
        try:
            with open(exportfull, 'w') as exp:
                exp.write("# " + rosdev['username'] + "@" + identity + ": "
                          + exportcmd + "\n")
                if timestamp:
                    exp.write(response)
                else:
                    no_ts = response.splitlines(1)[1:]
                    exp.writelines(no_ts)
                exp.close()
        except Exception as export_error:
            if SHELLMODE:
                device.close()
                sys.exit("Export file error: " + str(export_error))
            safe_fail(module, device, msg=str(export_error),
                      description='error writing to export file')

    if SHELLMODE:
        device.close()
        print export_dir
        print export_file
        sys.exit(0)

    safe_exit(module, device, changed=changed,
              export_file=export_file, export_dir=export_dir,
              identity=identity, software_id=software_id)

if __name__ == '__main__':
    SHELLOPTS = parse_opts(sys.argv)
    if 'shellmode' in SHELLOPTS:
        SHELLMODE = True
    main()
