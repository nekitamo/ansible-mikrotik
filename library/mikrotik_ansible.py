# coding: utf-8
"""Common MikroTik RouterOS modules library"""

import sys
import re

HAS_SSHCLIENT = True
SHELLMODE = False
MIKROTIK_MODULES = '[github.com/nekitamo/ansible-mikrotik]: 2017.03.20'

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
    options = {}
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
            options[arg] = val
    if 'help' not in options:
        if 'hostname' not in options:
            sys.exit("Hostname is required, specify with --hostname=<hostname>")
        if 'username' not in options:
            options['username'] = 'admin'
        if 'password' not in options:
            options['password'] = None
        if 'timeout' not in options:
            options['timeout'] = 30
        if 'port' not in options:
            options['port'] = 22
    return options

def device_connect(module, device, rosdev):
    """open ssh connection with or without ssh keys"""
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
                sys.exit("SSH error: " + str(ssh_error))
            safe_fail(module, device, msg=str(ssh_error),
                      description='error opening ssh connection to device')

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

def parse_facts(device, mtfacts, command, pfx=""):
    """executes a command and returns dict"""
    _stdin, stdout, _stderr = device.exec_command(command)
    mtfacts = {}
    for line in stdout.readlines():
        if ':' in line:
            fact, value = line.partition(":")[::2]
            fact = fact.replace('-', '_')
            if pfx not in fact:
                mtfacts[pfx + fact.strip()] = str(value.strip())
            else:
                mtfacts[fact.strip()] = str(value.strip())
    return mtfacts

def vercmp(ver1, ver2):
    """quick and dirty version comparison from stackoverflow"""
    def normalize(ver):
        return [int(x) for x in re.sub(r'(\.0+)*$', '', ver).split(".")]
    return cmp(normalize(ver1), normalize(ver2))
