# ckanext-odatabcn - CKAN extension for Open Data BCN customizations

`ckanext-odatabcn` provides Open Data BCN its custom appearance as well as some new functionalities. It contains two different plugins.

## Plugins

### OdatabcnPlugin
Includes all custom templates, translations, CSS and jQuery to adapt the CKAN interface to Barcelona's City Council style guide.

It also provides additional functionalities:
* Load drupal comments system into datasets. This was adapted from [ckan-canada](https://github.com/open-data/ckanext-canada) so it inserts Drupal nodes on package creation instead of executing commands periodically.
* Obtaining the number of downloads per resource
* Calculating monthly added and deactivated datasets
* Dataset catalogue download in CSV format. This CSV can be accessed from the URL **/cataleg.csv** of your CKAN installation.

#### Commands

This plugin also enables console commands that are executed through cron jobs:
 - `paster odatabcn update-tracking`: update resource ids on the tracking_summary table
 - `paster odatabcn update-dataset-total`: update the number of datasets published and deactivated last month on the odb_dataset_total custom table
 - `paster odatabcn get-new-tags`: check all active tags against the i18n "es" language file to check for missing translations and e-mail the list to the account added on the "email_to" configuration option.
 - `paster odatabcn submit-resource-to-datapusher`: submits a resource identified by "resource_id" to the datastore through datapusher. Adapted from ckan/ckanext/datapusher/cli.py `_submit` method which only allows all resources from a dataset to be submitted instead of a single one.
 
The shell scripts that are included on crontab can be found inside the `scripts` folder.

### EditFieldsPlugin

Hides internal use dataset fields to non-authenticated users.

This plugin also includes extra fields for each dataset's related organization and its parent provided by `ckanext-hierarchy` on dataset search actions. This is required to avoid executing API calls for each dataset returned in order to print its organization, as it conducts to a huge performance loss.

## Requirements

This extension requires CKAN version **2.7**. It hasn't been tested on previous or later versions.

The dataset commenting system requires a Drupal 7 installation with the [opendata_package](https://github.com/open-data/opendata_package) module installed and access to the drupal database from CKAN. 

It also requires the following CKAN extensions along with their requirements:
* stats
* ckanext-scheming
* ckanext-fluent
* ckanext-qa

## Installation
To install ckanext-odatabcn:
1. Execute the following SQL 
1. Activate your CKAN virtual environment, for example:
    `. /usr/lib/ckan/default/bin/activate`
	`cd /usr/lib/ckan/default/src`

2. Install the ckanext-odatabcn Python package into your virtual environment:
    `pip install -e "git+https://github.com/AjuntamentdeBarcelona/ckanext-odatabcn.git#egg=ckanext-odatabcn"`

3. Add `odatabcn` and `editfields` to the `ckan.plugins` setting in your CKAN config file (by default the config file is located at `/etc/ckan/default/production.ini`).

4. Restart CKAN. For example if you've deployed CKAN with Apache on Ubuntu:
     `sudo service apache2 reload`

## Configuration


### `ckan.drupal.url`

Connection URL to Drupal database. Required to save datasets as nodes in Drupal and enable dataset comments.

## Contributing

You are welcome to contribute to this repository, but please read the CONTRIBUTING guidelines.

## License

This extension is published under the GNU Affero General Public License v3 (see LICENSE).