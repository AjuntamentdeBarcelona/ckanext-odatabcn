# -*- coding: utf-8 -*-

import ckan.plugins as p
import datetime
import gettext
import logging
import mmap
import os 
import pickle
import requests
import sys

from ckan import model
from ckan.lib.cli import CkanCommand
from ckan.lib.mailer import mail_recipient
from pylons import config

missed_translations = set()

class MyFallback(gettext.NullTranslations):
	def gettext(self, msg):
		missed_translations.add(msg)
		return msg

class MyTranslations(gettext.GNUTranslations, object):
	def __init__(self, *args, **kwargs):
		super(MyTranslations, self).__init__(*args, **kwargs)
		self.add_fallback(MyFallback())

class Odatabcn(CkanCommand):
	'''
	Links download data stored on the tracking_summary table with its resources

	Use:
		paster odatabcn update-tracking -c /etc/ckan/default/production.ini
			- Insert resource ids on the tracking_summary table.
		
		paster odatabcn update-dataset-total -c /etc/ckan/default/production.ini
			- Insert the number of datasets published and deactivated last month
			  on the odb_dataset_total custom table.
		
		paster odatabcn get-new-tags -c /etc/ckan/default/production.ini
			- Check all active tags against the i18n "es" language file to check for missing translations
			  and e-mail the list to the account added on the "email_to" configuration option.
			
		paster odatabcn submit-resource-to-datapusher resource_id -c /etc/ckan/default/production.ini
			- Submits a resource identified by "resource_id" to the datastore through datapusher.
			  Adapted from ckan/ckanext/datapusher/cli.py _submit method which only allows all resources
			  from a dataset to be submitted instead of a single one.
		
	'''

	summary = __doc__.split('\n')[0]
	usage = __doc__
	min_args = 0
	max_args = 2

	def __init__(self, name):
		reload(sys)
		sys.setdefaultencoding('utf-8')
		super(Odatabcn, self).__init__(name)

	def command(self):
		#Parse command line arguments and call appropriate method
		if not self.args or self.args[0] in ['--help', '-h', 'help']:
			print self.usage
			sys.exit(1)

		cmd = self.args[0]
		self._load_config()

		# Initialise logger after the config is loaded, so it is not disabled
		self.log = logging.getLogger(__name__)

		if cmd == 'update-tracking':
			self.update_tracking()
		elif cmd == 'update-dataset-total':
			self.update_dataset_total()
		elif cmd == 'get-new-tags':
			self.get_new_tags()
		elif cmd == 'submit-resource-to-datapusher':
			self.submit_resource_to_datapusher(self.args[1])
		else:
			self.log.error('Command %s not recognized' % (cmd,))

	def update_tracking(self):
		
		# Insert resource ids
		sql = '''UPDATE tracking_summary ts
				SET resource_id = (SELECT CASE WHEN r.id IS NOT NULL THEN r.id
					WHEN split_part(t.url, '/', 8) LIKE 'resource' THEN  split_part(t.url, '/', 9)
					ELSE split_part(t.url, '/', 8)
					END AS resource_id
					FROM tracking_summary t 
					LEFT JOIN resource r ON r.url = t.url AND r.state = 'active' 
					WHERE t.tracking_type='resource' AND t.url = ts.url AND t.tracking_date = ts.tracking_date
					ORDER BY created ASC LIMIT 1)
				WHERE resource_id IS NULL
				AND tracking_type = 'resource';'''
		model.Session.execute(sql)
		model.Session.commit()
		print 'Resource IDs have been updated on tracking_summary'
		
		# Insert absolute view count
		sql_count = '''UPDATE tracking_summary ts
					SET count_absolute = (SELECT COUNT(*)
						FROM tracking_raw r
						WHERE r.url = ts.url
						AND CAST(r.access_timestamp as Date) = ts.tracking_date)
					WHERE ts.count_absolute IS NULL;'''
		model.Session.execute(sql_count)
		model.Session.commit()
		print 'Absolute view counts have been updated on tracking_summary'
		
	def update_dataset_total(self):
	
		first_day = datetime.date.today().replace(day=1)
		last_month_last = first_day - datetime.timedelta(days=1)
		last_month = last_month_last.replace(day=1)
		
		month = last_month.month
		year = last_month.year
		
		sql = '''SELECT * 
					FROM odb_dataset_total
					WHERE month = {0}
					AND year = {1}'''
		sql = sql.format(month, year)
		result = model.Session.execute(sql).fetchall()
		
		if len(result) > 0:
			
			print 'Dataset totals for last month are already saved to database'
		
		else:

			# Get total for previous month
			sql_previous_total = '''SELECT SUM(published) - SUM(deleted) AS total 
									FROM odb_dataset_total'''
			result = model.Session.execute(sql_previous_total).fetchall()
			previous_total = result[0]['total']
			
			print 'Previous total: %s' % previous_total
			
			# Current dataset total
			sql_current_total = '''SELECT COUNT(id) AS total
									FROM package 
									WHERE state = 'active' 
										AND NOT PRIVATE;'''
			result = model.Session.execute(sql_current_total).fetchall()
			current_total = result[0]['total']
			
			print 'Current total: %s' % (current_total)
			
			# Number of datasets published last month
			sql_published = '''SELECT COUNT(p.id) AS total 
								FROM package p
								INNER JOIN package_extra e ON p.id = e.package_id
								WHERE key LIKE 'fecha_publicacion'
									AND p.state = 'active'
									AND NOT PRIVATE
									AND to_date(value, 'YYYY-MM-DD') BETWEEN '{0}' AND '{1}';'''
			sql_published = sql_published.format(last_month, last_month_last)
			result = model.Session.execute(sql_published).fetchall()
			published_total = result[0]['total']
			
			print 'Number of datasets published between %s and %s: %s' % (last_month, last_month_last, published_total)
			
			# Number of unpublished or deleted datasets
			deleted_total = current_total - previous_total - published_total
			print 'Number of datasets deleted between %s and %s: %s' % (last_month, last_month_last, deleted_total)
			
			# Insert row in DDBB
			sql_insert = '''INSERT INTO odb_dataset_total (month, year, published, deleted)
						VALUES ({0}, {1}, {2}, {3});'''
			sql_insert = sql_insert.format(month, year, published_total, deleted_total)
			model.Session.execute(sql_insert)
			model.Session.commit()
			print 'Dataset totals for last month have been saved to database'
			
	def get_new_tags(self):
		
		sql = '''SELECT DISTINCT t.name AS tag
					FROM tag t
					INNER JOIN package_tag_revision pt ON pt.tag_id =  t.id 
					INNER JOIN package p ON p.id = pt.package_id 
                    WHERE pt.state = 'active'
						AND pt.expired_timestamp > '9999-01-01'
                        AND p.state = 'active'
						ORDER BY t.name ASC;'''
		results = model.Session.execute(sql).fetchall()

		if len(results) > 0:
		
			path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'i18n')

			#Use gettext to be able to set a custom fallback class
			lang = gettext.translation(
				"ckanext-" + self.command_name,
				localedir=path,
				languages=["es"],
				class_=MyTranslations
			)
			lang.install()
			
			for row in results:
				_(row['tag'])
			
			email_message = 'The following tags have no translation:\n'
			for tag in missed_translations:
				email_message = '%s\n* %s' % (email_message, tag)
				
			print(email_message)
			
			#E-mail missing tag list to account configured on "email_to"
			email_to = config.get('email_to')
			tags_email = {'recipient_name': '',
                      'recipient_email': email_to,
                      'subject': self.command_name + ': dataset tags', 
                      'body': email_message}
			mail_recipient(**tags_email)
			
			print '\nAn e-mail has been sent to %s' % (email_to)

		else:
			print 'There are no new tags'
			
	def submit_resource_to_datapusher(self, resource_id):
	
		user = p.toolkit.get_action('get_site_user')({'model': model, 'ignore_auth': True}, {})
		datapusher_submit = p.toolkit.get_action('datapusher_submit')
		
		print ('Submitting %s...' % resource_id),
		data_dict = {
			'resource_id': resource_id,
			'ignore_hash': True,
		}

		if datapusher_submit({'user': user['name']}, data_dict):
			print 'OK'
		else:
			print 'Fail'
