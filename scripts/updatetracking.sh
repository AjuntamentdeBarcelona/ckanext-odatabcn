#! /bin/bash
. /usr/lib/ckan/default/bin/activate
cd /usr/lib/ckan/default/src/ckanext-odatabcn
paster --plugin=ckanext-odatabcn odatabcn update-tracking --config=/etc/ckan/default/production.ini