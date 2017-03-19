#!/usr/bin/env bash
set -eu

mgmt_lan="192.168.88"
work_lan="10.0.0"
test_dir=test
vdi="https://www.mikrotik.com/download"

[ -f mikrotik_routers ] && exit 1

dpkg -s virtualbox > /dev/null || sudo apt install virtualbox # required
mkdir -p $test_dir && cd $test_dir && mkdir -p VMs
if [ $# -eq 0 ]; then
  dl="https:$(wget -q -O- $vdi | grep -Po '(?<=a href=")[^"]*/routeros/[^"]*\.vdi[^"]*' | head -n1)"
  wget -nv -cN $dl
  chrhd=$(basename $dl)
else
  chrhd="$1"
fi
echo "CHR disk image: $chrhd"
VBoxManage list hostonlyifs | grep -q vboxnet0 || VBoxManage hostonlyif create #vboxnet0
VBoxManage hostonlyif ipconfig vboxnet0 --ip $mgmt_lan.254 # management network
VBoxManage list dhcpservers | grep -q vboxnet0 || VBoxManage dhcpserver add --ifname vboxnet0 \
    --ip $mgmt_lan.254 --netmask 255.255.255.0 --lowerip $mgmt_lan.101 --upperip $mgmt_lan.200
VBoxManage dhcpserver modify --ifname vboxnet0 --enable
VBoxManage list hostonlyifs | grep -q vboxnet1 || VBoxManage hostonlyif create #vboxnet1
VBoxManage hostonlyif ipconfig vboxnet1 --ip $work_lan.1

echo "[mikrotik_routers]" > ../test-routers
for vm in {1..3}; do
  chrvm="chr$vm"
  VBoxManage createvm --name $chrvm --ostype "Other_64" --basefolder $(pwd)/VMs --register
  VBoxManage createhd --filename $(pwd)/VMs/$chrvm/$chrvm-hd.vdi --diffparent $(pwd)/$chrhd
  VBoxManage storagectl $chrvm --name "SATA1" --add sata --controller IntelAHCI
  VBoxManage storageattach $chrvm --storagectl "SATA1" --port 0 --device 0 --type hdd \
      --medium $(pwd)/VMs/$chrvm/$chrvm-hd.vdi
  VBoxManage modifyvm $chrvm --memory 128 --boot1 disk --boot2 none --boot3 none --boot4 none
  VBoxManage modifyvm $chrvm --nic1 hostonly --nictype1 virtio --hostonlyadapter1 vboxnet0
  VBoxManage modifyvm $chrvm --nic2 hostonly --nictype2 virtio --hostonlyadapter2 vboxnet1 \
      --nicpromisc2 allow-all
  VBoxManage modifyvm $chrvm --nic3 nat --nictype3 virtio --cableconnected3 off
  VBoxManage startvm $chrvm --type headless
  sleep 1
  echo "$mgmt_lan.10$vm" >> ../test-routers
done

echo "Waiting for boot..."
for up in {1..60}; do
  ping -qnc 1 $mgmt_lan.101 &&
    ping -qnc 1 $mgmt_lan.102 &&
      ping -qnc 1 $mgmt_lan.103 && break
done

echo -e "\nVirtual routers ready..."
exit 0
