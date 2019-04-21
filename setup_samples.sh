#!/bin/bash

git submodule init
git submodule foreach git pull origin master

mkdir ~/workspace
ln -s `pwd`/data ~/workspace/stock_data

sh setup/install.sh
sh setup/setup.sh
