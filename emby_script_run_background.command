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

#后台运行
screenName="jellyfin"

if [ $(screen -ls | grep -c $screenName) -ne 0 ]; then 
	screen -S $screenName -X quit
fi

screen -dmS $screenName
screen -x $screenName -p 0 -X stuff "python3 embyToLocalPlayer.py"
screen -x $screenName -p 0 -X stuff $'\n'