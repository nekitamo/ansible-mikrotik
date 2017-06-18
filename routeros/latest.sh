#!/usr/bin/env bash
set -eu

# first run gets 1.5GB of files!
ros_repo=routeros
ros_latest="https://www.mikrotik.com/download"

cd $ros_repo > /dev/null 2>&1 || ros_repo=.
wget -q -O- $ros_latest |
grep -Po "(?<=a href=\")[^\"]*/routeros/[^\"]*" |
  while read pkg; do
    ver="$(echo $pkg | grep -Po '(?<=routeros/)[^/]*')"
    if echo $ver | grep -qv rc; then 
      mkdir -p $ver
      wget -nv -cNP $ver https:$pkg
      if echo $pkg | grep -q winbox; then
        wbv="$(echo $pkg | grep -Po '(?<=winbox/)[^/]*')"
        cp -u $ver/winbox.exe $ver/winbox-$wbv.exe
      fi
    fi
  done
find . -name "all_packages*.zip" |
  while read f; do
    ver="$(echo $f | grep -Po '(?<=\./)[^/]*')"
    arch="$(echo $f | grep -Po '(?<=all_packages-).*(?=-)')"
    mkdir -p $ver/$arch
    unzip -q -u $f -d $ver/$arch || rm $f
  done
find . -maxdepth 2 -name "dude*.npk" |
  while read n; do
    ver="$(echo $n | grep -Po '(?<=/).*(?=/)')"
    arch="$(echo $n | grep -Po '(?<=-).*(?=\.)' | grep -Eo '[a-z]{3,}' || echo 'x86' )"
    cp -u $n ./$ver/$arch/$(basename $n)
 done
#find . -maxdepth 1 -type d -ctime +90 -regex ".*[0-9]" -exec rm -rf {} \;
exit 0
