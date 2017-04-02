# ansible-mikrotik
[Ansible](https://www.ansible.com/) library for [MikroTik](https://mikrotik.com/) [RouterOS](https://mikrotik.com/software) network device management with python modules that can also be used in shell scripts. It was designed with following use-cases in mind:
* detailed device information (facts) gathering (**mikrotik_facts.py**),
* configuration backup and change management (**mikrotik_export.py**),
* RouterOS upgrades and package management (**mikrotik_package.py**),
* ~~direct command execution or script upload (**mikrotik_command.py**).~~ _work in progress..._

Internet access is not necessary for package management, however you have to create local package repository either manually or by using one of the included shell scripts as described later in the 3rd step.
## 1. Basic prerequisites installation (debian/ubuntu):
Install stable version of Ansible, for example by adding its [Launchpad](https://launchpad.net/~ansible/+archive/ubuntu/ansible) repository on ubuntu:
```sh
sudo apt-add-repository ppa:ansible/ansible
apt update
apt install ansible git
```
## 2. Download the ansible-mikrotik library:
```sh
git clone https://github.com/nekitamo/ansible-mikrotik.git
cd ansible-mikrotik
```
## 3. Initialize local RouterOS package repository
You can either use the following (more complicated) script which downloads less files (~550 MB) and creates includable ansible vars (versions.yml) with actual package versions for current and bugfix release trees:
```sh
routeros/routeros.sh
```
Or you can use this much simpler script that will download practically everything from MikroTik's latest software web page (1.5+ gigabytes):
```sh
./ros-latest.sh
```
Both scripts can be used at will to create proper directory structure for use with mikrotik_package.py module. Also, both will probably have to be constantly updated as MikroTik web pages evolve with time...
## 4. Run some tests to see if it works
Running the included shell script 'create-vms.sh' should create a local test environment with 3 virtual MikroTik routers (aka CHRs). You can use them to run some example ansible playbooks like so:
```sh
ansible-playbook -i test-routers example-mtfacts.yml
ansible-playbook -i test-routers example-exp2git.yml
ansible-playbook -i test-routers example-upgrade.yml
```
There is also a cleanup script 'destroy-vms.sh' which will shut down and delete virtual routers once you're done testing.
## Shell mode usage (w/o ansible) on ubuntu:
Simply use `mikrotik_<module>.py` modules from `/library` folder with shell command line options like so:
```sh
library/mikrotik_facts.py --hostname=192.168.88.1 --verbose
```
Run it without arguments for basic usage info or open it with a text editor for detailed built-in ansible documentation.
## Troubleshooting
### SSH client error: No module named paramiko
This means you need to install python's paramiko module. As simply apt-getting `python-paramiko` will probably just lead to problem described in the next chapter, run both commands at its end to get the latest version of paramiko right away.
### FutureWarning: CTR mode needs counter parameter, not IV
If you see the above warning than your distribution's version of paramiko is, besides being pretty old, also broken and you should upgrade it:
```sh
sudo apt install build-essential libssl-dev libffi-dev python-dev python-pip
sudo -H pip install --upgrade paramiko
```