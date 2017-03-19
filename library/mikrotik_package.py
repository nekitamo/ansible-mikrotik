#!/usr/bin/env python
# coding: utf-8
"""MikroTik RouterOS package manager"""

import os
import socket
import time
from mikrotik_ansible import *

DOCUMENTATION = """
---
module: mikrotik_package
short_description: MikroTik RouterOS package manager
description:
    - MikroTik RouterOS package manager with desired state provisioning
    - Supports automatic install/enable/disable package operations
return_data:
    - changed
    - enabled_packages
    - disabled_packages
    - routeros_version
options:
    repository:
        description:
            - Preexisting directory with uncompressed RouterOS <version>/<architecture> package tree
            - Created either manually or with the included shell script (routeros/latest.sh)
        required: false
        default: 'routeros'
    packages:
        description:
            - List of desired RouterOS packages after provisioning
            - If omitted, currently enabled packages will be kept after upgrade or downgrade
        required: false
        default: null
    version:
        description:
            - desired RouterOS version, no change if omitted (use to add/remove packages)
        required: false
        default: null 
    reboot:
        description:
            - Reboot device after package provisioning and wait until it gets online
        required: false
        default: false
    port:
        description:
            - SSH listening port of the MikroTik RouterOS device
        required: false
        default: 22
    hostname:
        description:
            - IP Address or hostname of the MikroTik RouterOS device
        required: true
        default: null
    username:
        description:
            - Username used to login to the MikroTik RouterOS device
        required: false
        default: ansible
    password:
        description:
            - Password used to login to the MikroTik RouterOS device
        required: false
        default: null

"""
EXAMPLES = """
# example playbook, requires RouterOS repo in ./routeros

- name: Mikrotik RouterOS package management
  hosts: mikrotik_routers
  include_vars: routeros_auth.yml
  connection: local

  tasks:

  - name: upgrade routeros packages
    mikrotik_package:
      hostname: "{{ inventory_hostname }}"
      username: "{{ routeros_username }}"
      password: "{{ routeros_password }}"
      reboot: yes
      version: 6.38.3

"""
RETURN = """
routeros_version:
    description: actual RouterOS version after task execution
    returned: always
    type: string
enabled_packages:
    description: actual list of enabled packages after task execution
    returned: always
    type: list
disabled_packages:
    description: actual list of disabled packages after task execution
    returned: always
    type: list
"""
SHELL_USAGE = """

mikrotik_package.py --shellmode --hostname=<hostname> --repository=<path>
               [--packages=<pkg1,pkg2...>] [--reboot[=true|false|yes|no]]
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
    reboot_timeout = 90
    changed = False
    if not SHELLMODE:
        module = AnsibleModule(
            argument_spec=dict(
                repository=dict(default='routeros', type='path'),
                packages=dict(default=None, type='list'),
                version=dict(default=None, type='str'),
                reboot=dict(default=False, type='bool'),
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
        repository = os.path.expanduser(module.params['repository'])
        packages = module.params['packages']
        version = module.params['version']
        reboot = module.params['reboot']
        rosdev['hostname'] = socket.gethostbyname(module.params['hostname'])
        rosdev['username'] = module.params['username']
        rosdev['password'] = module.params['password']
        rosdev['port'] = module.params['port']
        rosdev['timeout'] = module.params['timeout']

    elif len(sys.argv) > 1:
        if not HAS_SSHCLIENT:
            sys.exit("SSH client error: " + str(import_error))
        rosdev['hostname'] = socket.gethostbyname(SHELLOPTS['hostname'])
        rosdev['username'] = SHELLOPTS['username']
        rosdev['password'] = SHELLOPTS['password']
        rosdev['port'] = SHELLOPTS['port']
        rosdev['timeout'] = SHELLOPTS['timeout']
        repository = 'routeros'
        packages = None
        version = None
        reboot = False
        module = None
        if 'repository' in SHELLOPTS:
            repository = os.path.expanduser(SHELLOPTS['repository'])
        if 'packages' in SHELLOPTS:
            packages = SHELLOPTS['packages'].split(",")
        if 'version' in SHELLOPTS:
            version = SHELLOPTS['version']
        if 'reboot' in SHELLOPTS:
            reboot = SHELLOPTS['reboot']
    else:
        sys.exit(SHELL_USAGE)

    device = paramiko.SSHClient()
    device.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    turn = 1
    while turn:
        if turn != 2:
            device_connect(module, device, rosdev)

        response = sshcmd(module, device, cmd_timeout,
                          ":put [/system resource get version]")
        device_version = str(response.split(" ")[0])
        enabled_packages = parse_terse(device, "name",
                "system package print terse without-paging where disabled=no")
        disabled_packages = parse_terse(device, "name",
                "system package print terse without-paging where disabled=yes")
        for pkg in enabled_packages:
            if 'routeros' in pkg:
                enabled_packages.remove(pkg)
                break
        if not packages:
            packages = list(enabled_packages)
        if turn > 1:
            break
        res = sshcmd(module, device, cmd_timeout,
                     'system package print count-only where scheduled~"scheduled"')
        if not '0' in res:
            res = sshcmd(module, device, cmd_timeout,
                         'system package unschedule [find scheduled~"scheduled"]')
            changed = True
        if not version:
            version = device_version
        if vercmp(device_version, version) > 0:
            downgrade = True
        else:
            downgrade = False
            if vercmp(version, "6.37") >= 0:
                for pkg in packages:
                    if 'wireless-' in pkg:
                        packages.remove(pkg)
                        packages.append('wireless')
                        break
        response = sshcmd(module, device, cmd_timeout,
                          ":put [/system resource get architecture-name]")
        arch = response.lower()
        if 'system' not in packages:
            packages.append('system')

        upload = []
        enable = []
        disable = []
        for pkg in packages:
            if pkg in disabled_packages:
                enable.append(pkg)
                if device_version != version:
                    upload.append(pkg)
            elif pkg not in enabled_packages:
                upload.append(pkg)
            elif device_version != version:
                upload.append(pkg)
        for pkg in enabled_packages:
            if pkg not in packages:
                disable.append(pkg)

        for pkg in upload:
            if arch == 'x86':
                pkg = pkg + "-" + version + ".npk"
            else:
                pkg = pkg + "-" + version + "-" + arch + ".npk"
            ppath = os.path.join(repository, version, arch, pkg)
            if not os.path.exists(ppath):
                if SHELLMODE:
                    device.close()
                    sys.exit("package not found: " + str(pkg))
                safe_fail(module, device, msg=str(pkg),
                          description='package not found')
            else:
                sftp = device.open_sftp()
                sftp.put(ppath, pkg)
                sftp.close()
                changed = True

        for pkg in disable:
            res = sshcmd(module, device, cmd_timeout,
                         'system package disable [find name~"'
                         + pkg + '"]')
            changed = True

        for pkg in enable:
            res = sshcmd(module, device, cmd_timeout,
                         'system package enable [find name~"'
                         + pkg + '"]')
            changed = True

        if not changed:
            break
        if reboot:
            if downgrade:
                cmd = "system package downgrade"
            else:
                cmd = "system reboot"
            res = sshcmd(module, device, cmd_timeout, cmd)
            device.close()
            time.sleep(reboot_timeout)
            turn += 1
        turn += 1

    if SHELLMODE:
        device.close()
        print "routeros_version: %s" % device_version
        if changed:
            print "enabled_packages: %s" % ', '.join(enabled_packages)
            print "disabled_packages: %s" % ', '.join(disabled_packages)
        sys.exit(0)

    safe_exit(module, device, changed=changed,
              routeros_version=device_version,
              enabled_packages=enabled_packages,
              disabled_packages=disabled_packages)

if __name__ == '__main__':
    SHELLOPTS = parse_opts(sys.argv)
    if 'shellmode' in SHELLOPTS:
        SHELLMODE = True
    main()
