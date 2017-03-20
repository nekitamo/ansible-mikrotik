# ansible-mikrotik
[Ansible](https://www.ansible.com/) library for [MikroTik](https://mikrotik.com/) [RouterOS](https://mikrotik.com/software) network device management with python modules that can also be used in shell scripts. It was designed with following use-cases in mind:
* detailed device information (facts) gathering (**mikrotik_facts.py**),
* RouterOS upgrades and package management (**mikrotik_package.py**),
* configuration backup and change management (**mikrotik_export.py**),
* ~~direct command execution or script upload (**mikrotik_command.py**).~~ _work in progress..._

Internet access is not necessary for the package management module, however you have to create a local package repository either manually or by using one of the included shell scripts as described in 3rd step.
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
`cd ansible-mikrotik`
```
## 3. Initialize local RouterOS package repository
You can either use the following (more complicated) script which will download less files (~550 MB), but also create includable ansible tasks (current.yml, bugfix.yml) with actual package versions for both release trees:
```sh
routeros/routeros.sh
```
Or you can use this much simpler script that will download practically everything from MikroTik's latest software web page (1.5+ gigabytes):
```sh
./ros-latest.sh
```
Both scripts can be used at will to create the proper directory structure for use with mikrotik_package.py module. Also, both will probably have to be constantly updated as MikroTik web pages change with time...
## 4. Run some tests to see if it works
Running the included shell script 'create-vms.sh' will create a local test environment with 3 virtual MikroTik routers (aka CHRs). You can use them to run some example ansible playbooks like so:
```sh
ansible-playbook -i test-routers gather-facts.yml
```
There is also a cleanup script 'destroy-vms.sh' which will shut down and delete virtual routers once you're done testing.
## Shell mode usage (w/o ansible):
Simply use `mikrotik_<module>.py` modules from `/library` folder with shell command line options like so:
```sh
library/mikrotik_facts.py --help
library/mikrotik_facts.py --shellmode --hostname=192.168.88.1
```