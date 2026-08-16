#!/bin/bash
  set -euo pipefail
  program=001010111
  # Runtime: each substitution is one reduction rule, rewriting the encoding
  # itself. leaf is 1, stem 01x, fork 001xy, and applying f to x is 0fx.
  function reduce {
    perl -pe 'while($_=~/000/){s/0001001(1|0(?1)(?1))(1|0(?2)(?2))(1|0(?3)(?3))001/00$3/g;s/0001001(1|0(?1)(?1))(1|0(?2)(?2))(1|0(?3)(?3))01/0$2/g;s/0001001(1|0(?1)(?1))(1|0(?2)(?2))(1|0(?3)(?3))1/$1/g;s/000101011(1|0(?1)(?1))(1|0(?2)(?2))/${2}/g;s/0001010011(1|0(?1)(?1))(1|0(?2)(?2))(1|0(?3)(?3))/0${1}0${2}${3}/g;s/000101(1|0(?1)(?1))0011(1|0(?2)(?2))(1|0(?3)(?3))/00${1}${3}${2}/g;s/000101(1|0(?1)(?1))(1|0(?2)(?2))(1|0(?3)(?3))/00$1${3}0$2$3/g;s/00011(1|0(?1)(?1))(1|0(?2)(?2))/$1/g}'
  }
  # Conversions: string <=> encoded tree
  function of_list () {
    while read -r line; do
      echo -n "001$line"
    done
    echo 1
  }
  function to_list () {
    sed 's/1$//' | perl -pe "s/0(1|0(?1)(?1))/\1\n/g" | sed -e 's/^01//g;$d'
  }
  function of_string () {
    perl -ne 'printf "%vb\n", $_'  | tr . '\n' | rev | sed 's/0/a/g;s/1/001011/g;s/a/0011/g;s/$/1/' | of_list
  }
  function to_string () {
    to_list | sed 's/1$//;s/0011/a/g;s/001011/1/g;s/a/0/g' | rev | echo "ibase=2;$(cat)" | bc | while read -r N; do printf "\\$(printf '%03o' "$N")"; done
  }
  
  fifo=$(mktemp -u)
  mkfifo "$fifo"
  (echo -n 0$program; of_string) | reduce "$fifo" | to_string
  rm -f "$fifo"
 