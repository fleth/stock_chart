#!/bin/bash

git submodule init
git submodule foreach git pull origin master

sh setup/install.sh
sh setup/setup.sh
