# freeradius/Dockerfile

FROM freeradius/freeradius-dev:v3.2.x

# Copy your custom configuration files
COPY ./sites-available/default /etc/raddb/sites-available/default
COPY ./mods-available/rest /etc/raddb/mods-available/rest

# Enable the default site
RUN ln -s /etc/raddb/mods-available/rest /etc/raddb/mods-enabled/rest

# Expose the RADIUS ports
EXPOSE 1812/udp
EXPOSE 1813/udp

CMD ["radiusd", "-f", "-Xx"]