#!/usr/bin/env bash
set -eu

vdi="https://www.mikrotik.com/download"
mgmt_lan="192.168.88"
work_lan="10.0.0"
test_dir=test

[ -f test-routers ] && exit 1
dpkg -s virtualbox > /dev/null || sudo apt install virtualbox # required

mkdir -p $test_dir && cd $test_dir && mkdir -p VMs
if [ $# -eq 0 ]; then # download latest vdi
  dl="https:$(wget -q -O- $vdi | grep -Po '(?<=a href=")[^"]*/routeros/[^"]*\.vdi[^"]*' | head -n1)"
  wget -nv -cN $dl
  chrhd="$(pwd)/$(basename $dl)"
else # local vdi filename for offline use (./create-vms.sh <vdi_file>)
  chrhd="$1"
fi
echo -e "CHR disk image: $chrhd\nSetting up VirtualBox networking..."
VBoxManage list hostonlyifs | grep -q vboxnet0 || VBoxManage hostonlyif create #vboxnet0
VBoxManage hostonlyif ipconfig vboxnet0 --ip $mgmt_lan.254 # management network
VBoxManage list dhcpservers | grep -q vboxnet0 || VBoxManage dhcpserver add --ifname vboxnet0 \
    --ip $mgmt_lan.254 --netmask 255.255.255.0 --lowerip $mgmt_lan.101 --upperip $mgmt_lan.200
VBoxManage dhcpserver modify --ifname vboxnet0 --enable
VBoxManage list hostonlyifs | grep -q vboxnet1 || VBoxManage hostonlyif create #vboxnet1
VBoxManage hostonlyif ipconfig vboxnet1 --ip $work_lan.1
echo "[mikrotik_routers]" > ../test-routers
for vm in {1..3}; do
  chrvm="chr$vm"; echo
  VBoxManage createvm --name $chrvm --ostype "Other_64" --basefolder $(pwd)/VMs --register
  VBoxManage createhd --filename $(pwd)/VMs/$chrvm/$chrvm-hd.vdi --diffparent $chrhd
  VBoxManage storagectl $chrvm --name "SATA1" --add sata --controller IntelAHCI
  VBoxManage storageattach $chrvm --storagectl "SATA1" --port 0 --device 0 --type hdd \
      --medium $(pwd)/VMs/$chrvm/$chrvm-hd.vdi
  VBoxManage modifyvm $chrvm --memory 128 --boot1 disk --boot2 none --boot3 none --boot4 none
  VBoxManage modifyvm $chrvm --nic1 hostonly --nictype1 virtio --hostonlyadapter1 vboxnet0
  VBoxManage modifyvm $chrvm --nic2 hostonly --nictype2 virtio --hostonlyadapter2 vboxnet1 \
      --nicpromisc2 allow-all
  VBoxManage modifyvm $chrvm --nic3 nat --nictype3 virtio --cableconnected3 off
  VBoxManage startvm $chrvm --type headless > /dev/null
  echo -n "Waiting for '$chrvm' to start: "
  for up in {1..60}; do
    echo -n "."
    ping -qnc 1 $mgmt_lan.10$vm > /dev/null && break
  done
  if [ "$up" -eq "60" ]; then
    echo -e " TIMEOUT!\nNo response from $chrvm, deployment aborted."; exit 1
  fi
  echo " OK."
  echo "$mgmt_lan.10$vm sys_id=$chrvm" >> ../test-routers
done

exit 0
test_key=test-rsa
test_vault=test-vault.yml
test_vpf=test-password
test_password="test"
dpkg -s pwgen > /dev/null || sudo apt install pwgen # required
echo -n "Generating test keys and password... "
echo "$test_password" > $test_vpf
echo "private_key: |" > $test_vault
ssh-keygen -qf $test_key -t rsa -N '' || exit 1
while read ln; do
    echo "  $ln" >> $test_vault
done <$test_key
echo "admin_password: $(pwgen -H $test_key -s 10 1)" >> $test_vault
ansible-vault encrypt --vault-password-file=$test_vpf $test_vault
