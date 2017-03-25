#!/usr/bin/env bash
set -eu

ros_scheme="https:"
ros_archive="$ros_scheme//www.mikrotik.com/download/archive"
ros_repo=.

if [ $# -eq 0 ]; then
    echo "Usage: archive.sh <routeros version>"
fi

cd $ros_repo > /dev/null 2>&1 || ros_repo=.
wget -q -O- $ros_archive |
grep -Po "(?<=a href=\")[^\"]*/routeros/[^\"]*" |
  while read pkg; do
    # version extraction
    version="$(echo $pkg | grep -Po '(?<=routeros/)[^/]*')"
    if [ "$version" == "$1" ]; then
      mkdir -p $version
      if echo $pkg | grep -q "/$version/all_packages-"; then
        arch="$(echo $pkg | grep -Po '(?<=all_packages-).*(?=-)')"
        new=$(wget -nv -cNP $version $ros_scheme$pkg 2>&1)
        if [ "${#new}" -gt "1" ]; then
          echo "- new package $(basename $pkg) downloaded into $ros_repo/$version"
          mkdir -p $version/$arch
          echo "  extracting $(basename $pkg) into $ros_repo/$version/$arch"
          unzip -qu $version/$(basename $pkg) -d $version/$arch || rm $version/$(basename $pkg)
        else
          echo "- package $(basename $pkg) already in $ros_repo/$version"
        fi
      fi
    fi
  done
exit 0