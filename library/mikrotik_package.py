#!/usr/bin/env python
# coding: utf-8
"""MikroTik RouterOS package manager"""

import sys
import re
import os
import socket
import time

HAS_SSHCLIENT = True
SHELLMODE = False
SHELLDEFS = {
    'username': 'admin',
    'password': '',
    'timeout': 60,
    'port': 22,
    'repository': 'routeros',
    'packages': None,
    'version': None,
    'reboot': False
#   TODO:
#   'reboot_timeout': 60,
#   'reboot_wait': true,
#   'default_packages': ['system', 'security', 'dhcp']
}
MIKROTIK_MODULE = '[github.com/nekitamo/ansible-mikrotik] v2017.03.23'
DOCUMENTATION = """
---
module: mikrotik_package
short_description: MikroTik RouterOS package manager
description:
    - MikroTik RouterOS package manager for desired state provisioning
    - Supports automatic install/enable/disable package operations with local package repository
    - If you create router user 'ansible' with ssh-key you can omit username/password in playbooks    
return_data:
    - routeros_version
    - enabled_packages
    - disabled_packages
    - scheduled_packages
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
      version: 6.38.5

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
scheduled_packages:
    description: list of packages to be enabled or disabled after next reboot
    returned: always
    type: list
"""
SHELL_USAGE = """
mikrotik_package.py --hostname=<hostname> --repository=<path>
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
else:
    # ansible parameters on stdin?
    if sys.stdin.isatty():
        SHELLMODE = True

def safe_fail(module, device=None, **kwargs):
    """closes device before module fail"""
    if device:
        device.close()
    module.fail_json(**kwargs)

def safe_exit(module, device=None, **kwargs):
    """closes device before module exit"""
    if device:
        device.close()
    module.exit_json(**kwargs)

def parse_opts(cmdline):
    """returns SHELLMODE command line options as dict"""
    options = SHELLDEFS
    for opt in cmdline:
        if opt.startswith('--'):
            try:
                arg, val = opt.split("=", 1)
            except ValueError:
                arg = opt
                val = True
            else:
                if val.lower() in ('no', 'false', '0'):
                    val = False
                elif val.lower() in ('yes', 'true', '1'):
                    val = True
            arg = arg[2:]
            if arg in options or arg == 'hostname':
                options[arg] = val
            else:
                print SHELL_USAGE
                sys.exit("Unknown option: --%s" % arg)
    if 'hostname' not in options:
        print SHELL_USAGE
        sys.exit("Hostname is required, specify with --hostname=<hostname>")
    return options

def device_connect(module, device, rosdev):
    """open ssh connection with or without ssh keys"""
    try:
        rosdev['hostname'] = socket.gethostbyname(rosdev['hostname'])
    except socket.gaierror as dns_error:
        if SHELLMODE:
            sys.exit("Hostname error: " + str(dns_error))
        safe_fail(module, device, msg=str(dns_error),
                  description='error getting device address from hostname')
    if SHELLMODE:
        sys.stdout.write("Opening SSH connection to %s:%s... "
                         % (rosdev['hostname'], rosdev['port']))
        sys.stdout.flush()
    try:
        device.connect(rosdev['hostname'], username=rosdev['username'],
                       password=rosdev['password'], port=rosdev['port'],
                       timeout=rosdev['timeout'])
    except Exception:
        try:
            device.connect(rosdev['hostname'], username=rosdev['username'],
                           password=rosdev['password'], port=rosdev['port'],
                           timeout=rosdev['timeout'], allow_agent=False,
                           look_for_keys=False)
        except Exception as ssh_error:
            if SHELLMODE:
                sys.exit("failed!\nSSH error: " + str(ssh_error))
            safe_fail(module, device, msg=str(ssh_error),
                      description='error opening ssh connection to %s' % rosdev['hostname'])
    if SHELLMODE:
        print "succes."

def sshcmd(module, device, timeout, command):
    """executes a command on the device, returns string"""
    try:
        _stdin, stdout, _stderr = device.exec_command(command, timeout=timeout)
    except Exception as ssh_error:
        if SHELLMODE:
            sys.exit("SSH command error: " + str(ssh_error))
        safe_fail(module, device, msg=str(ssh_error),
                  description='SSH error while executing command')
    response = stdout.read()
    if not 'bad command name ' in response:
        if not 'syntax error ' in response:
            if not 'failure: ' in response:
                return response.rstrip()
    if SHELLMODE:
        print "Command: " + str(command)
        sys.exit("Error: " + str(response))
    safe_fail(module, device, msg=str(ssh_error),
              description='bad command name or syntax error')

def parse_terse(device, key, command):
    """executes a command and returns list"""
    _stdin, stdout, _stderr = device.exec_command(command)
    vals = []
    for line in stdout.readlines():
        if key in line:
            val = line.split(key+'=')[1]
            vals.append(val.split(' ')[0])
    return vals

def parse_facts(device, command, pfx=""):
    """executes a command and returns dict"""
    _stdin, stdout, _stderr = device.exec_command(command)
    facts = {}
    for line in stdout.readlines():
        if ':' in line:
            fact, value = line.partition(":")[::2]
            fact = fact.replace('-', '_')
            if pfx not in fact:
                facts[pfx + fact.strip()] = str(value.strip())
            else:
                facts[fact.strip()] = str(value.strip())
    return facts

def vercmp(ver1, ver2):
    """quick and dirty version comparison from stackoverflow"""
    def normalize(ver):
        return [int(x) for x in re.sub(r'(\.0+)*$', '', ver).split(".")]
    return cmp(normalize(ver1), normalize(ver2))

def main():
    rosdev = {}
    upload = []
    enable = []
    disable = []
    cmd_timeout = 15
    reboot_timeout = 30
    default_packages = ['system', 'security']
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
                password=dict(default='', type='str'),
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

    else:
        if not HAS_SSHCLIENT:
            sys.exit("SSH client error: " + str(import_error))
        rosdev['hostname'] = SHELLOPTS['hostname']
        rosdev['username'] = SHELLOPTS['username']
        rosdev['password'] = SHELLOPTS['password']
        rosdev['port'] = SHELLOPTS['port']
        rosdev['timeout'] = SHELLOPTS['timeout']
        repository = os.path.expanduser(SHELLOPTS['repository'])
        packages = None
        if SHELLOPTS['packages']:
            packages = SHELLOPTS['packages'].split(",")
        version = SHELLOPTS['version']
        reboot = SHELLOPTS['reboot']
        module = None

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
        scheduled_packages = parse_terse(device, "name",
            'system package print terse without-paging where scheduled~"scheduled"')
        for pkg in enabled_packages:
            if 'routeros' in pkg:
                enabled_packages.remove(pkg)
                break
        if not packages:
            packages = list(enabled_packages)
        if turn > 1:
            break
        if not version:
            version = device_version
        diff = vercmp(device_version, version)
        if diff > 0:
            downgrade = True
            if SHELLMODE:
                print "Downgrading RouterOS: %s to %s" % (device_version, version)
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
        if SHELLMODE and diff < 0:
            print "Upgrading RouterOS: %s to %s (%s)" % (device_version, version, arch)
        if arch == 'x86_64':
            arch = 'x86'
        for def_pkg in default_packages:
            if def_pkg not in packages:
                packages.append(def_pkg)

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
        if SHELLMODE and upload:
            print "Uploading package(s): %s" % ', '.join(upload)
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
                uploaded = sftp.listdir()
                if pkg in uploaded and SHELLMODE:
                    print "- package %s found, overwritting..." % pkg
                try:
                    sftp.put(ppath, pkg)
                except Exception as put_error:
                    if SHELLMODE:
                        sys.exit("Upload failed, SFTP error: " + str(put_error))
                    safe_fail(module, device, msg=str(put_error),
                              description='SFTP error, check disk space')
                sftp.close()
                changed = True
        if not upload:
            if scheduled_packages and (disable or enable):
                _res = sshcmd(module, device, cmd_timeout,
                    'system package unschedule [find scheduled~"scheduled"]')
                changed = True
            if SHELLMODE and disable:
                print "Disabling package(s): %s" % ', '.join(disable)
            for pkg in disable:
                _res = sshcmd(module, device, cmd_timeout,
                              'system package disable [find name~"'
                              + pkg + '"]')
                changed = True
            if SHELLMODE and enable:
                print "Enabling package(s): %s" % ', '.join(enable)
            for pkg in enable:
                _res = sshcmd(module, device, cmd_timeout,
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
            _res = sshcmd(module, device, cmd_timeout, cmd)
            device.close()
            if SHELLMODE:
                print "Waiting %d seconds for reboot (/%s)..." % (reboot_timeout, cmd)
            time.sleep(reboot_timeout)
            turn += 1
        turn += 1

    if SHELLMODE:
        device.close()
        print "routeros_version: %s" % device_version
        print "enabled_packages: %s" % ', '.join(enabled_packages)
        if disabled_packages:
            print "disabled_packages: %s" % ', '.join(disabled_packages)
        if scheduled_packages:
            print "scheduled_packages: %s" % ', '.join(scheduled_packages)
        if not changed:
            print "Nothing changed."
        sys.exit(0)

    safe_exit(module, device, changed=changed,
              routeros_version=device_version,
              enabled_packages=enabled_packages,
              disabled_packages=disabled_packages,
              uploaded_packages=upload)

if __name__ == '__main__':
    if len(sys.argv) > 1 or SHELLMODE:
        print "Ansible MikroTik Library %s" % MIKROTIK_MODULE
        SHELLOPTS = parse_opts(sys.argv)
        SHELLMODE = True
    main()
