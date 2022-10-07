#!/bin/bash
PATH=/bin:/usr/bin:/usr/local/bin:${PATH}

realpath_function() {
	if ! command -v realpath &>/dev/null; then
		[[ $1 = /* ]] && echo "$1" || echo "$PWD/${1#./}"
	else
		realpath "$1"
	fi
}

script_folder=$(dirname "$(realpath_function "$0")")
echo run in "$script_folder"
cd "$script_folder" || (echo cd faild && exit)

python3 embyToLocalPlayer.py
