#!/bin/bash
os=`uname -s`
if [[ $os = "Linux" ]]; then
	g++ -Wl,-rpath -Wl,'$ORIGIN' -L. -g -o demoraw demoraw.cpp -lnncam -lncurses
else
	clang++ -Wl,-rpath -Wl,. -L. -g -o demoraw demoraw.cpp -lnncam -lncurses
fi
