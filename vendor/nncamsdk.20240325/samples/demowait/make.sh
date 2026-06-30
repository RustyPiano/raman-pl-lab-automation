#!/bin/bash
os=`uname -s`
if [[ $os = "Linux" ]]; then
	g++ -Wl,-rpath -Wl,'$ORIGIN' -L. -g -o demowait demowait.cpp -lnncam
else
	clang++ -Wl,-rpath -Wl,. -L. -g -o demowait demowait.cpp -lnncam
fi
