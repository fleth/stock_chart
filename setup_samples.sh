#!/bin/bash

git submodule update -i
git submodule foreach git pull origin master

sh setup/install.sh
sh setup/setup_sample.sh
