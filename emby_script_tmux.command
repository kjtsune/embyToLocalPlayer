#!/bin/sh
PATH=/bin:/usr/bin:/usr/local/bin:${PATH}
realpath() {
	[[ $1 = /* ]] && echo "$1" || echo "$PWD/${1#./}"
}

script_folder=$(dirname $(realpath "$0"))
cd $script_folder

_=$(tmux kill-session -t "emby" 2>&1)
tmux new-session -d -s emby \; send-keys "python3 embyToLocalPlayer.py" Enter
