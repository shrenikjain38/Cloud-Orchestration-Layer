#!/bin/bash
# sudo apt-get update
# sudo apt-get install pymongo
# sudo apt-get install mongodb
# sudo service mongodb restart
cd ../src/
python test.py $1 $2 $3
