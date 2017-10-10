import datetime
import logging
import sys

from ckan import model
from ckan.lib.cli import CkanCommand


class Odatabcn(CkanCommand):
	'''
	Links download data stored on the tracking_summary table with its resources

	Use:
		paster odatabcn update-tracking
			- Update resource ids on the tracking_summary table
		
		paster odatabcn update-dataset-total
			- Update the number of datasets published and deactivated last month
			  on the odb_dataset_total custom table
	'''

	summary = __doc__.split('\n')[0]
	usage = __doc__
	min_args = 0
	max_args = 1

	def __init__(self, name):
		super(Odatabcn, self).__init__(name)

	def command(self):
		"""
		Parse command line arguments and call appropriate method.
		"""
		if not self.args or self.args[0] in ['--help', '-h', 'help']:
			print self.usage
			sys.exit(1)

		cmd = self.args[0]
		self._load_config()

		# Initialise logger after the config is loaded, so it is not disabled.
		self.log = logging.getLogger(__name__)

		if cmd == 'update-tracking':
			self.update_tracking()
		elif cmd == 'update-dataset-total':
			self.update_dataset_total()
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
					LEFT JOIN resource r ON r.url = t.url
					WHERE t.tracking_type='resource' AND r.state = 'active' AND t.url = ts.url AND t.tracking_date = ts.tracking_date)
				WHERE resource_id IS NULL
				AND tracking_type = 'resource';'''
		model.Session.execute(sql)
		model.Session.commit()
		print 'Se han actualizado los IDs de los recursos en la tabla tracking_summary'
		
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
		
		