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

_=$(tmux kill-session -t "emby" 2>&1)
tmux new-session -d -s emby \; send-keys "python3 embyToLocalPlayer.py" Enter
