#!/usr/bin/env python
# coding: utf-8
"""MikroTik RouterOS backup and change manager"""

import sys
import re
import socket
import os

HAS_SSHCLIENT = True
SHELLMODE = False
SHELLDEFS = {
    'username': 'admin',
    'password': '',
    'timeout': 30,
    'port': 22,
    'export_dir': None,
    'export_file' : None,
    'backup_dir': None,
    'timestamp': False,
    'hide_sensitive': True,
    'local_file': False,
    'verbose': False
}
MIKROTIK_MODULE = '[github.com/nekitamo/ansible-mikrotik] v2017.03.28'
DOCUMENTATION = """
---

module: mikrotik_export
short_description: MikroTik RouterOS configuration export
description:
    - Exports full router configuration to a text file in export directory
    - By default no local export file is created on the router (enable with local_file: yes)
    - If you create router user 'ansible' with ssh-key you can omit username/password in playbooks
return_data:
    - identity
    - software_id
    - export_dir
    - export_file
    - backup_dir
    - backup_files
options:
    export_dir:
        description:
            - Directory where export_file is written after export
        required: true
        default: null
    export_file:
        description:
            - The name of the exported file, existing files are not overwritten
        required: true
        default: <identity>_<software_id>.rsc
    backup_dir:
        description:
            - Directory where backups are downloaded
        required: true
        default: null
    timestamp:
        description:
            - Leave default timestamp in export file (first line), disabled for version tracking
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
            - Exports via local_file option allways include timestamp in first line
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
    description: Returns filename of exported configuration
    returned: always
    type: string
backup_dir:
    description: Returns full os path where backups were downloaded
    returned: if backup_dir option was used
    type: string
backup_files:
    description: Returns list of downloaded backups
    returned: if backup_dir option was used
    type: list
"""
SHELL_USAGE = """
mikrotik_export.py --hostname=<hostname> --export_dir=<path>
                   --export_file=<filename> --backup_dir=<path>
                  [--timestamp=yes|no] [--hide_sensitive] [--verbose]
                  [--local_file] [--timeout=<timeout>] [--port=<port>]
                  [--username=<username>] [--password=<password>]
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
    backup_files = []
    cmd_timeout = 30
    changed = False
    if not SHELLMODE:
        module = AnsibleModule(
            argument_spec=dict(
                export_dir=dict(required=True, type='path'),
                export_file=dict(required=False, type='str'),
                backup_dir=dict(required=False, type='path'),
                timestamp=dict(default=False, type='bool'),
                hide_sensitive=dict(default=True, type='bool'),
                local_file=dict(default=False, type='bool'),
                verbose=dict(default=False, type='bool'),
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
        export_dir = os.path.expanduser(module.params['export_dir'])
        export_file = module.params['export_file']
        backup_dir = module.params['backup_dir']
        if backup_dir:
            backup_dir = os.path.expanduser(backup_dir)
            backup_dir = os.path.realpath(backup_dir)
        timestamp = module.params['timestamp']
        hide_sensitive = module.params['hide_sensitive']
        local_file = module.params['local_file']
        verbose = module.params['verbose']
        rosdev['hostname'] = module.params['hostname']
        rosdev['username'] = module.params['username']
        rosdev['password'] = module.params['password']
        rosdev['port'] = module.params['port']
        rosdev['timeout'] = module.params['timeout']

    else:
        if not HAS_SSHCLIENT:
            sys.exit("SSH client error: " + str(import_error))
        if not SHELLOPTS['export_dir']:
            print SHELL_USAGE
            sys.exit("export_dir required, specify with --export_dir=<path>")
        export_dir = os.path.expanduser(SHELLOPTS['export_dir'])
        rosdev['hostname'] = SHELLOPTS['hostname']
        rosdev['username'] = SHELLOPTS['username']
        rosdev['password'] = SHELLOPTS['password']
        rosdev['port'] = SHELLOPTS['port']
        rosdev['timeout'] = SHELLOPTS['timeout']
        hide_sensitive = SHELLOPTS['hide_sensitive']
        export_file = SHELLOPTS['export_file']
        backup_dir = SHELLOPTS['backup_dir']
        if backup_dir:
            backup_dir = os.path.expanduser(backup_dir)
            backup_dir = os.path.realpath(backup_dir)
        timestamp = SHELLOPTS['timestamp']
        local_file = SHELLOPTS['local_file']
        verbose = SHELLOPTS['verbose']
        module = None

    device = paramiko.SSHClient()
    device.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    device_connect(module, device, rosdev)

    version = sshcmd(module, device, cmd_timeout,
                     ":put [/system resource get version]")
    response = sshcmd(module, device, cmd_timeout, "system identity print")
    identity = str(response.split(": ")[1])
    identity = identity.strip()
    software_id = sshcmd(module, device, cmd_timeout,
                         ":put [ /system license get software-id ]")
    if not software_id:
        software_id = rosdev['hostname']
    if not export_file:
        export_file = identity + "_" + software_id + ".rsc"
    export_dir = os.path.realpath(export_dir)
    exportfull = os.path.join(export_dir, export_file)
    exportcmd = "export"
    if hide_sensitive:
        exportcmd += " hide-sensitive"
    if verbose:
        exportcmd += " verbose"
    if local_file:
        exportcmd += " file=ansible-export"
        changed = True
    response = sshcmd(module, device, cmd_timeout, exportcmd)
    if local_file:
        sftp = device.open_sftp()
        sftp.get("/ansible-export.rsc", exportfull)
        sftp.close()
    else:
        try:
            with open(exportfull, 'w') as exp:
                exp.write("# " + rosdev['username'] + "@" + identity +
                          ", RouterOS " + version +": " + exportcmd + "\n")
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
    if backup_dir:
        sftp = device.open_sftp()
        listdir = sftp.listdir()
        for item in listdir:
            if item.endswith('.backup'):
                bkp = os.path.join(backup_dir, item)
                if not os.path.exists(bkp):
                    sftp.get(item, bkp)
                backup_files.append(item)
        sftp.close()

    if SHELLMODE:
        device.close()
        print "export_dir: %s" % export_dir
        print "export_file: %s" % export_file
        if backup_dir:
            print "backup_dir: %s" % backup_dir
            print "backup_files: %s" % ', '.join(backup_files)
        sys.exit(0)

    safe_exit(module, device, changed=changed,
              export_file=export_file, export_dir=export_dir,
              backup_files=backup_files, backup_dir=backup_dir,
              identity=identity, software_id=software_id)

if __name__ == '__main__':
    if len(sys.argv) > 1 or SHELLMODE:
        print "Ansible MikroTik Library %s" % MIKROTIK_MODULE
        SHELLOPTS = parse_opts(sys.argv)
        SHELLMODE = True
    main()
