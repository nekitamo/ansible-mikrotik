#!/usr/bin/env bash
set -eu
#
# This script automatically dowloads bugfix+current RouterOS packages
# from MikroTik web and creates an off-line repository for use with
# mikrotik_package.py Ansible module. It may need some adjustments
# from time to time as target MikroTik web changes (ros_archive).
#
script_version="v2017.03.05 by https://github.com/nekitamo"
ros_scheme="https:"
ros_archive="$ros_scheme//www.mikrotik.com/download/archive"
ros_repo=routeros
ros_log=routeros.log
#
# What follows is a template that creates two ansible tasks which can
# be included in your playbooks if you want latest routeros versions:
#
# - include: routeros/current.yml
#              or
# - include: routeros/bugfix.yml
#
ros_yml=$(cat <<EOF
---
- name: upgrade routeros packages
  mikrotik_package:
#    repository: $ros_repo
    hostname: "{{ inventory_hostname }}"
#    username: "{{ routeros_username }}"
#    password: "{{ routeros_password }}"
#    reboot: yes
    version:
EOF
) # always keep "version:" in last line!
changed="False"

cd $ros_repo > /dev/null 2>&1 || ros_repo=.
echo "# MikroTik RouterOS repository script $script_version" > $ros_log
echo "START: $(date --rfc-3339=seconds) in $(pwd)" >> $ros_log
wget -q -O- $ros_archive |
grep -Po "(?<=a href=\")[^\"]*/routeros/[^\"]*|(?<=>)[^<]*release tree[^<]*" |
  while read pkg; do
    # main processing loop for "*/routeros/*" urls
    if echo $pkg | grep -q "release tree"; then
      # release tree extraction
      release=$(echo ${pkg,,} | cut -d" " -f1)
      version="unknown"; retry=500 # skip pkgs before giving up search
      echo -n "$pkg: " >> $ros_log
    else
      if [ "$version" == "unknown" ]; then
        # version extraction
        version="$(echo $pkg | grep -Po '(?<=routeros/)[^/]*')"
        mkdir -p $version
        ln -snf $version $release
        echo "$version" >> $ros_log
        echo "$ros_yml $version" > $release.yml
        #echo -n "routeros_$release=$version "
      fi
      if echo $pkg | grep -q "/$version/"; then
        # extract all_packages zips into <ver>/<arch> subfolders
        if echo $pkg | grep -q "/$version/all_packages-"; then
          arch="$(echo $pkg | grep -Po '(?<=all_packages-).*(?=-)')"
          new=$(wget -nv -cNP $version $ros_scheme$pkg 2>&1)
          if [ "${#new}" -gt "1" ]; then
            echo "- new package $(basename $pkg) downloaded into $ros_repo/$version" >> $ros_log
            mkdir -p $version/$arch
            echo "  extracting $(basename $pkg) into $ros_repo/$version/$arch" >> $ros_log
            unzip -qu $version/$(basename $pkg) -d $version/$arch || rm $version/$(basename $pkg)
            if [ "$changed" == "False" ]; then changed="True"; fi
          else
            echo "- package $(basename $pkg) already in $ros_repo/$version" >> $ros_log
          fi
        fi
        if echo $pkg | grep -q "/$version/routeros-"; then
          # download routeros combo npks into <ver>/<arch> subfolders
          arch="$(echo $pkg | grep -Po '(?<=routeros-).*(?=-)')"
          mkdir -p $version/$arch
          new=$(wget -nv -cNP $version/$arch $ros_scheme$pkg 2>&1)
          if [ "${#new}" -gt "1" ]; then
            echo "- new package $(basename $pkg) downloaded into $ros_repo/$version/$arch" >> $ros_log
            if [ "$changed" == "False" ]; then changed="True"; fi
          else
            echo "- package $(basename $pkg) already in $ros_repo/$version/$arch" >> $ros_log
          fi
        fi
        if echo $pkg | grep -Eq ".*/$version/dude-.*\.npk"; then
          # downloads only x86 dude npk, no urls for other architectures?
          arch="$(echo $pkg | grep -Po '(?<=-).*(?=\.)' | grep -Eo '[a-z]{3,}' || echo 'x86' )"
          mkdir -p $version/$arch
          new=$(wget -nv -cNP $version/$arch $ros_scheme$pkg 2>&1)
          if [ "${#new}" -gt "1" ]; then
            echo "- new package $(basename $pkg) downloaded into $ros_repo/$version/$arch" >> $ros_log
            if [ "$changed" == "False" ]; then changed="True"; fi
          else
            echo "- package $(basename $pkg) already in $ros_repo/$version/$arch" >> $ros_log
          fi
        fi
      else
        ((retry--))
        if [ "$retry" -eq "0" ]; then
          #echo "changed=$changed"
          break
        fi
      fi
    fi
  done
echo -e "STOP: $(date --rfc-3339=seconds)" >> $ros_log
exit 0