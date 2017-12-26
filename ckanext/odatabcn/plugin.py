import ckan.logic.auth.update as update_auth
import logging
import psycopg2
import json
import sys

from ckan.lib.cli import parse_db_config
from ckan import plugins
from ckan import model
from ckan.plugins import toolkit
from ckan.plugins import interfaces
from ckan.model import domain_object
from ckan.lib.plugins import DefaultTranslation
from ckanext.odatabcn import validators
from collections import OrderedDict

log = logging.getLogger(__name__)

## Custom authorization functions
def logged_in_users_only(context, data_dict=None):	
	if context.get('user'):
		return {'success': True}
	else:
		return {'success': False,
				'msg': 'Only users are allowed to access user profiles'}

class OdatabcnPlugin(plugins.SingletonPlugin, DefaultTranslation, toolkit.DefaultDatasetForm):
	plugins.implements(plugins.IConfigurer)
	plugins.implements(plugins.IRoutes, inherit=True)
	plugins.implements(plugins.ITranslation)
	plugins.implements(plugins.IFacets, inherit=True)
	plugins.implements(plugins.IDomainObjectModification, inherit=True)
	plugins.implements(plugins.IResourceController, inherit=True)
	plugins.implements(plugins.IAuthFunctions, inherit=True)
	plugins.implements(plugins.IValidators)

	# IConfigurer
	def update_config(self, config_):
		toolkit.add_template_directory(config_, 'templates')
		toolkit.add_public_directory(config_, 'public')
		toolkit.add_resource('fanstatic', 'odatabcn')

	def before_map(self, map):
		map.connect(
			'cataleg', '/cataleg.csv',
			controller='ckanext.odatabcn.controllers:CSVController',
			action='view'
		)
		return map

	# Add custom facets
	def dataset_facets(self, facets_dict, package_type):
		facets_dict['geolocation'] = toolkit._('Geolocation')
		facets_dict['frequency'] = toolkit._('Frequency')
		return facets_dict
		
	def organization_facets(self, facets_dict, organization_type, package_type):
		facets_dict['geolocation'] = toolkit._('Geolocation')	
		facets_dict['frequency'] = toolkit._('Frequency')
		return facets_dict

	# Add created datasets to Drupal table to enable comments
	def notify(self, entity, operation=None):
		if operation == model.domain_object.DomainObjectOperation.new:
			
			reload(sys)
			sys.setdefaultencoding('utf-8')

			dbc = parse_db_config('sqlalchemy.url')
			ckan_conn_string = "host='%s' dbname='%s' user='%s' password='%s'" % (dbc['db_host'], dbc['db_name'], dbc['db_user'], dbc['db_pass'])

			dbd = parse_db_config('ckan.drupal.url')
			drupal_conn_string = "host='%s' dbname='%s' user='%s' password='%s'" % (dbd['db_host'], dbd['db_name'], dbd['db_user'], dbd['db_pass'])

			ckan_conn = psycopg2.connect(ckan_conn_string)
			drupal_conn = psycopg2.connect(drupal_conn_string)
			ckan_cursor = ckan_conn.cursor()
			drupal_cursor = drupal_conn.cursor()
			
			log.debug('entity title_translated: %s', entity.title_translated)
			log.debug('entity notes_translated: %s', entity.notes_translated)
			log.debug('entity id: %s', entity.id)
			log.debug('entity name: %s', entity.name)

			titles = json.loads(entity.title_translated)
			descriptions = json.loads(entity.notes_translated)
			title_en = ''
			if 'en' in titles:
				title_en = titles['en']
			title_es = ''
			if 'es' in titles:
				title_es = titles['es']
			title_ca = ''
			if 'ca' in titles:
				title_ca = titles['ca']
			desc_en = ''
			if 'en' in descriptions:
				desc_en = descriptions['en']
			desc_es = ''
			if 'es' in descriptions:
				desc_es = descriptions['es']
			desc_ca = ''
			if 'ca' in descriptions:
				desc_ca = descriptions['ca']
			print "Inserting package %s: %s %s %s: %s %s %s %s" % (entity.id, entity.name, title_en, title_es, title_ca, desc_en, desc_es, desc_ca)
			try:
				drupal_cursor.execute("""insert into opendata_package (pkg_id,pkg_name,pkg_title_en,pkg_title_es,pkg_title_ca,pkg_description_en,pkg_description_es,pkg_description_ca) values (%s, %s, %s, %s, %s, %s, %s, %s)""", (entity.id, self.format_drupal_string(entity.name), self.format_drupal_string(title_en), self.format_drupal_string(title_es), self.format_drupal_string(title_ca), self.format_drupal_string(desc_en), self.format_drupal_string(desc_es), self.format_drupal_string(desc_ca)))
				drupal_conn.commit()
			except psycopg2.DataError, e:
				self.logger.warn('Postgresql Database Exception %s', e.message)

			drupal_conn.commit()
			drupal_cursor.close()
			drupal_conn.close()

			ckan_cursor.close()
			ckan_conn.close()

	def format_drupal_string(self, ds):
		dstr = ds.encode('utf-8')
		return dstr
	
	# Add resource downloads to resource_show
	def before_show(context, resource_dict):
		reload(sys)
		sys.setdefaultencoding('utf-8')
		dbc = parse_db_config('sqlalchemy.url')
		ckan_conn_string = "host='%s' dbname='%s' user='%s' password='%s'" % (dbc['db_host'], dbc['db_name'], dbc['db_user'], dbc['db_pass'])
		ckan_conn = psycopg2.connect(ckan_conn_string)
		ckan_cursor = ckan_conn.cursor()
		ckan_cursor.execute("""select sum(count), sum(count_absolute) from tracking_summary t inner join resource r on t.resource_id=r.id where tracking_type='resource' AND r.id=%s""", (resource_dict['id'],))
		row = ckan_cursor.fetchone()

		if len(row) != 0:
			resource_dict['downloads'] = row[0]
			resource_dict['downloads_absolute'] = row[1]
		else:
			resource_dict['downloads'] = '0'
			resource_dict['downloads_absolute'] = '0'

		ckan_cursor.close()
		ckan_conn.close()
	
	# Override CKAN authorization functions
	def get_auth_functions(self):
		auth_functions = {
				'package_activity_list': update_auth.package_update,
				'user_show': logged_in_users_only,
				'user_list': logged_in_users_only
			}
		
		return auth_functions
	

	# Custom validators
	def get_validators(self):
		return {
			'required_if_public': validators.required_if_public,
		}
	