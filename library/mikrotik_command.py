#!/usr/bin/env python

import os
import sys
import socket

DOCUMENTATION = """
---

module: mikrotik_command
short_description: Execute single or multiple MikroTik RouterOS CLI commands
description:
    - Execute one or more MikroTik RouterOS CLI commands via ansible or shell
    - Execute multiple commands from a file or save them as a RouterOS script
    - Authenticate via username/password or by using ssh keys
return_data:
    - changed
    - stdout
    - stdout_lines
options:
    command:
        description:
            - MikroTik command to execute or script filename with multiple commands
        required: yes
        default: null
    hostname:
        description:
            - IP Address or hostname of the MikroTik device
        required: true
        default: null
    run_block:
        description:
            - Execute commands from file specified in command option
        required: no
        choices: true, false
        default: false
    upload_script:
        description:
            - Upload commands from file specified in command and save as a script
        required: no
        default: false
    test_change:
        description:
            - Test for configuration changes after command execution (slow)
        required: no
        default: false
    upload_file:
        description:
            - Upload specified file before command/script execution
        required: no
        default: null
    port:
        description:
            - SSH listening port of the MikroTik device
        required: no
        default: 22
    username:
        description:
            - Username used to login for the device
        required: no
        default: ansible
    password:
        description:
            - Password used to login to the device
        required: no
        default: null

"""
EXAMPLES = """

  - name: Upload and assign ssh key
    mikrotik_command:
      hostname: "{{ inventory_hostname }}"
      username: ansible
      password: ""
      upload_file: "~/.ssh/id_rsa.pub"
      command: "/user ssh-keys import public-key-file=id_rsa.pub user=ansible"

  - name: Reboot router
    mikrotik_command:
      hostname: "{{ inventory_hostname }}"
      command: "/system reboot;"

"""
RETURN = """
stdout:
    description: Returns router response in a single string
    returned: always
    type: string
stdout_lines:
    description: Returns router response as a list of strings
    returned: always
    type: list
"""
SHELL_USAGE= """

mikrotik_command.py --shellmode --hostname=<hostname> --command=<command>
        [--run_block] [--upload_script] [--upload_file=<file>]
        [--port=<port>] [--username=<username>] [--password=<password>]

"""

try:
    HAS_SSHCLIENT = True
    import paramiko
except ImportError as ie:
    HAS_SSHCLIENT = False

try:
    shellmode = False
    from ansible.module_utils.basic import AnsibleModule
except ImportError:
    shellmode = True


def safe_fail(module, device=None, **kwargs):
    if device:
        device.close()
    module.fail_json(**kwargs)


def safe_exit(module, device=None, **kwargs):
    if device:
        device.close()
    module.exit_json(**kwargs)


def parse_opts(cmdline):
    opts = {}
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
            opts[arg] = val
    return opts


def sshcmd(module, device, timeout, command):
    try:
        stdin, stdout, stderr = device.exec_command(command,
                timeout=timeout)
    except Exception as e:
        if shellmode:
            sys.exit("SSH command error: " + str(e))
        safe_fail(module, device, msg=str(e),
                description='SSH error while executing command')
    response = stdout.read()
    if not 'bad command name ' in response:
        if not 'syntax error ' in response:
            if not 'failure: ' in response:
                return response.rstrip()
    if shellmode:
        device.close()
        print "Command: " + str(command)
        sys.exit("Error: " + str(response))
    safe_fail(module, device, msg=str(response),
            description='bad command name or syntax error')


def main():
    changed = True
    if not shellmode:
        module = AnsibleModule(
            argument_spec=dict(
                command=dict(required=True),
                run_block=dict(default=False, type='bool'),
                upload_script=dict(default=False, type='bool'),
                test_change=dict(default=False, type='bool'),
                upload_file=dict(default=None, type='path'),
                port=dict(default=22, type='int'),
                timeout=dict(default=30, type='float'),
                hostname=dict(required=True),
                username=dict(default='ansible', type='str'),
                password=dict(default=None, type='str'),
            ), supports_check_mode=False
        )
        if not HAS_SSHCLIENT:
            safe_fail(module, msg='There was a problem loading module: ',
                    error=str(ie))

        command = module.params['command']
        run_block = module.params['run_block']
        upload_script = module.params['upload_script']
        test_change = module.params['test_change']
        upload_file = os.path.expanduser(module.params['upload_file'])
        port = module.params['port']
        username = module.params['username']
        password = module.params['password']
        timeout = module.params['timeout']
        hostname = socket.gethostbyname(module.params['hostname'])

    elif len(sys.argv) > 1:
        if not HAS_SSHCLIENT:
            sys.exit("SSH client error: " + str(ie))
        if 'command' not in opts:
            sys.exit("Command required, specify with --command=<command>")
        command = opts['command']
        if 'hostname' not in opts:
            sys.exit("Hostname required, specify with --hostname=<hostname>")
        hostname = socket.gethostbyname(opts['hostname'])
        run_block = False
        upload_script = False
        test_change = False
        upload_file = None
        port = 22
        username = 'admin'
        password = None
        timeout = 30
        module = None
        if 'run_block' in opts:
            run_block = opts['run_block']
        if 'upload_script' in opts:
            upload_script = opts['upload_script']
        if 'test_change' in opts:
            test_change = opts['test_change']
        if 'upload_file' in opts:
            upload_file = os.path.expanduser(opts['upload_file'])
        if 'port' in opts:
            port = opts['port']
        if 'username' in opts:
            username = opts['username']
        if 'password' in opts:
            password = opts['password']
        if 'timeout' in opts:
            timeout = opts['timeout']
    else:
        sys.exit(SHELL_USAGE)

    device = paramiko.SSHClient()
    device.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        device.connect(hostname, username=username, password=password,
                port=port, timeout=timeout)
    except Exception:
        try:
            device.connect(hostname, username=username, password=password,
                    port=port, timeout=timeout, allow_agent=False,
                    look_for_keys=False)
        except Exception as e:
            if shellmode:
                sys.exit("SSH error: " + str(e))
            safe_fail(module, device, msg=str(e),
                  description='error opening ssh connection to device')

    response = sshcmd(module, device, timeout,
            '/user print terse where name="' + username + '"')
    if 'group=read' in response:
        changed = False
        test_change = False
        upload_script = False

    if test_change:
        before = sshcmd(module, device, timeout, "/export")

    if upload_file and os.path.isfile(upload_file):
        if changed:
            uploaded = os.path.basename(upload_file)
            sftp = device.open_sftp()
            sftp.put(upload_file, uploaded)
            sftp.close()
            response = sshcmd(module, device, timeout,
                '/file print terse without-paging where name="' + uploaded + '"')
        else:
            uploaded = "read only user!"
            response = ''
        if uploaded not in response:
            if shellmode:
                device.close()
                sys.exit("Error uploading file: " + uploaded)
            safe_fail(module, device, msg="upload failed!",
                description='error uploading file: ' + uploaded)

    if run_block or upload_script:
        response = ''
        try:
            command = os.path.expanduser(command)
            with open(command) as scriptfile:
                script = scriptfile.readlines()
                scriptfile.close()
        except Exception as e:
            if shellmode:
                device.close()
                sys.exit("Script file error: " + str(e))
            safe_fail(module, device, msg=str(e),
                  description='error opening script file')
        if upload_script:
            scriptname = os.path.basename(command)
            response += sshcmd(module, device, timeout,
                    '/system script remove [ find name="' + scriptname + '" ]')
            cmd = '/system script add name="' + scriptname + '" source="'
            for line in script:
                line = line.rstrip()
                line = line.replace("\\", "\\\\")
                line = line.replace("\"", "\\\"")
                line = line.replace("$", "\\$")
                cmd += line + "\\r\\n"
            response += sshcmd(module, device, timeout, cmd + '"')
        elif run_block:
            for cmd in script:
                if cmd[0]!="#":
                    rsp = sshcmd(module, device, timeout, cmd)
                    if rsp:
                        response += rsp + '\r\n'
    else:
        if upload_file and command == 'user ssh-keys import':
            response = sshcmd(module, device, timeout,
                '/user ssh-keys import public-key-file="' + uploaded
                + '" user=' + username)
        else:
            response = sshcmd(module, device, timeout, command)
        if response:
            response += '\r\n'

    if test_change:
        after = sshcmd(module, device, timeout, "/export")
        before = before.splitlines(1)[1:]
        after = after.splitlines(1)[1:]
        if len(before) == len(after):
            for b, a in zip(before, after):
                if a != b:
                    break
            else:
                changed = False

    if shellmode:
        device.close()
        print str(response)
        sys.exit(0)

    stdout_lines = []
    for line in response.splitlines():
        if line:
            stdout_lines.append(line.rstrip())

    safe_exit(module, device, stdout=response, stdout_lines=stdout_lines, changed=changed)


if __name__ == '__main__':
    opts = parse_opts(sys.argv)
    if 'shellmode' in opts:
        shellmode = True
    main()
