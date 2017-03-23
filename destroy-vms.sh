#!/usr/bin/env bash
set -eu

test_dir=test

[ -d $test_dir ] || exit 1
VBoxManage list runningvms | cut -d\" -f2 | grep chr |
  while read vm; do
    VBoxManage controlvm $vm poweroff
  done
VBoxManage list vms | cut -d\" -f2 | grep chr |
  while read vm; do
    VBoxManage unregistervm $vm
    rm -rf $test_dir/VMs/$vm
  done
VBoxManage dhcpserver remove -ifname vboxnet0
VBoxManage hostonlyif remove vboxnet0
VBoxManage hostonlyif remove vboxnet1
rm -rf $test_dir; rm test-routers

exit 0