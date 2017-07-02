#!/usr/bin/env bash
set -eu
#
# This script automatically dowloads bugfix+current RouterOS packages
# from MikroTik web and creates an off-line repository for use with
# mikrotik_package.py Ansible module. It may need some adjustments
# from time to time as target MikroTik web changes (ros_archive).
#
script_version="v2017.03.23 by https://github.com/nekitamo"
ros_scheme="https:"
ros_archive="$ros_scheme//www.mikrotik.com/download/archive"
ros_repo=routeros
ros_cleanup=180
ros_log=routeros.log
ros_versions=versions.yml
changed="False"

cd $ros_repo > /dev/null 2>&1 || ros_repo=.
echo "# MikroTik RouterOS repository script $script_version" > $ros_log
echo "START: $(date --rfc-3339=seconds) in $(pwd)" >> $ros_log
echo "---" > $ros_versions
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
        echo "routeros_$release: $version" >> $ros_versions
        # echo -n "routeros_$release=$version "
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
          # download dude npks (MT site finally fixed for non-x86 architectures)
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
if [ "$ros_cleanup" -gt "0" ]; then
  echo "CLEANUP: deleting subfolders older than $ros_cleanup day(s)..." >> $ros_log
  find . -maxdepth 1 -type d -ctime +$ros_cleanup -regex ".*[0-9]" -exec rm -rf {} \; >> $ros_log 2>&1
fi
echo "STOP: $(date --rfc-3339=seconds), repository size: $(du -hc | grep -v '\.' | cut -f1)" >> $ros_log
exit 0