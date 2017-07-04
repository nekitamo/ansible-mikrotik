# ansible-mikrotik
[Ansible](https://www.ansible.com/) library for [MikroTik](https://mikrotik.com/) [RouterOS](https://mikrotik.com/software) network device management with python modules that can also be used in shell scripts. It was designed with following use-cases in mind:
- [x] detailed device information (facts) gathering (**mikrotik_facts.py**),
- [x] configuration backup and change management (**mikrotik_export.py**),
- [x] RouterOS upgrades and package management (**mikrotik_package.py**),
- [ ] direct command execution or script upload (**mikrotik_command.py**).

Package management module works without internet access, however you need to create a local RouterOS package repository either manually or by using one of included shell scripts as described later in the 3rd step.
## 1. Basic prerequisites installation (Debian/Ubuntu):
Install stable version of Ansible, for example by adding its [Launchpad](https://launchpad.net/~ansible/+archive/ubuntu/ansible) repository on ubuntu:
```sh
sudo apt-add-repository ppa:ansible/ansible
sudo apt update
sudo apt install ansible git
```
## 2. Download the ansible-mikrotik library:
```sh
git clone https://github.com/nekitamo/ansible-mikrotik.git
cd ansible-mikrotik
```
## 3. Initialize local RouterOS package repository
You can either use the following (more complicated) script which downloads less files (~550 MB) and creates includable ansible vars (versions.yml) with actual package versions for current and bugfix release trees:
```sh
routeros/update.sh
```
Or you can use this much simpler script that will download practically everything from MikroTik's latest software web page (1.5+ gigabytes):
```sh
routeros/latest.sh
```
Both scripts can be used at will to create proper directory structure for use with mikrotik_package.py module. Also, both will probably have to be constantly updated as MikroTik web pages evolve with time...
## 4. Run some tests to see if it works
Running the included shell script 'create-vms.sh' should create a local test environment with 3 virtual MikroTik routers (aka CHRs). You can use them to run some example ansible playbooks like so:
```sh
./create-vms.sh
ansible-playbook -i test-routers example-mtfacts.yml
ansible-playbook -i test-routers example-exp2git.yml
ansible-playbook -i test-routers example-upgrade.yml
```
Try starting some of the playbooks multiple times and see what happens. There is also a cleanup script './destroy-vms.sh' which will shut down and delete virtual routers once you're done testing.
## 5. Some security considerations
There are three basic ways you can handle ssh authentication:
1. **plaintext** passwords in playbooks/scripts or
2. passwords encrypted with **ansible vault** or
3. omit passwords and just use **ssh keys**.

The included 'example-secure.yml' ansible playbook kind of walks you through all three. It starts with initial empty admin credentials to gain access to a 'blank' device, then sets new admin password from predefined credentials stored in encrypted ansible vault (test-vault.yml), and finally uploads admin's public ssh key which is later used instead of passwords.
## Shell mode usage (w/o ansible):
Simply use `mikrotik_<module>.py` modules from `/library` folder with shell command line options like so (ansible parameters and command line options are exactly the same):
```sh
library/mikrotik_facts.py --hostname=192.168.88.101 --verbose
```
Run it without arguments for basic usage info or open it with a text editor for detailed built-in ansible documentation.
## Useful tools - mactelnet
This simple tool included in standard ubuntu repositories enables you to just plug a new MikroTik device into your management network and configure it for basic IP connectivity without WinBox.
```sh
sudo apt install mactelnet-client
mndp # or mactelnet -l, wait for device discovery and note the mac-address and port:
#Searching for MikroTik routers... Abort with CTRL+C.
#
#IP              MAC-Address       Identity (platform version hardware) uptime
#0.0.0.0         8:0:27:4e:f2:9b   MikroTik (MikroTik 6.38.7 (bugfix) CHR)  up 0 days 0 hours   ether1
#^C
mactelnet -u admin -p '' <mac-address> # configure fixed ip address or dhcp-client via CLI:
#[admin@MikroTik] > ip dhcp-client add interface=<iface>
```
## Troubleshooting (Debian/Ubuntu)
### SSH client error: No module named paramiko
This means you need to install python's paramiko module. As simply apt-getting `python-paramiko` will probably just lead to problem described in the next chapter, run both commands at its end to get the latest version of paramiko right away. 
### FutureWarning: CTR mode needs counter parameter, not IV
If you see the above warning than your distribution's version of paramiko is, besides being pretty old, also broken and you should upgrade it:
```sh
sudo apt install build-essential libssl-dev libffi-dev python-dev python-pip
sudo -H pip install --upgrade paramiko
```
#### Offline upgrade
First, download everything you need into a new folder ("paramikopips") on a host with internet access:
```sh
mkdir paramiko
sudo -H pip download -r requirements.txt -d paramikopips
```
Then transfer this folder to the off-line host and run:
```sh
sudo -H pip install --no-index --find-links=paramikopips -r requirements.txt
```
Naturally, for this to work the off-line host should already have previously mentioned distribution packages. But if you have hosts w/o internet access you've probably already figured out the need for some kind of apt-mirror or similar device...