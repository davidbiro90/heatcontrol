FROM python:3.10-slim

# Szükséges csomagok telepítése
RUN pip install requests

# Mappa beállítása és fájlok másolása
WORKDIR /app
COPY heating_control.py /app
COPY run.sh /app
RUN chmod a+x /app/run.sh

# Indítási parancs
CMD ["/app/run.sh"]