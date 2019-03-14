#!/bin/bash


nohup sh -c './manage.py runserver 0.0.0.0:8000' &


while :
do
	./manage.py loadplugins
	./manage.py loadcomponents
	./manage.py runplugins
	sleep 600
done
