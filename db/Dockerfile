FROM postgres:latest

RUN mkdir /var/pg
RUN mkdir /var/pg/log
RUN mkdir /var/pg/backups

ADD cron /etc/cron.d/cron
ADD backup.sh /var/pg/backup.sh
ADD clean-backup.sh /var/pg/clean-backup.sh
ADD postgresql.conf /var/pg/postgresql.conf

# Give execution rights on the cron job
RUN chmod 0644 /etc/cron.d/cron
RUN chown -R postgres:postgres /var/pg
RUN chmod 760 /var/pg/backup.sh
RUN chmod 760 /var/pg/clean-backup.sh

CMD ["postgres", "-c", "config_file=/var/pg/postgresql.conf"]