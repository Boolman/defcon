FROM python:3.6-stretch
RUN mkdir /workspace
WORKDIR /workspace
COPY . .
RUN pip install -r requirements.txt
RUN chmod +x start.sh
RUN ./manage.py migrate &&\
	    ./manage.py migrate --run-syncdb &&\
	    ./manage.py loadplugins &&\
	    ./manage.py loadcomponents

EXPOSE 8000
CMD ./start.sh
