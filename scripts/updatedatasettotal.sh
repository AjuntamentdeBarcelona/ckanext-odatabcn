#! /bin/bash
. /usr/lib/ckan/default/bin/activate
cd /usr/lib/ckan/default/src/ckanext-odatabcn
paster --plugin=ckanext-odatabcn odatabcn update-dataset-total --config=/etc/ckan/default/production.ini