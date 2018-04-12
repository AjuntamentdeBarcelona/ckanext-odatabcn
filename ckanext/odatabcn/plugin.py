import ckan.logic.auth.update as update_auth
import logging
import psycopg2
import json
import sys
import pprint
import ckan.authz as authz

from ckan.lib.cli import parse_db_config
from ckan import plugins
from ckan import model
from ckan.plugins import toolkit
from ckan.plugins import interfaces
from ckan.model import domain_object
from ckan.model import package as _package
from ckan.lib.plugins import DefaultTranslation
from ckanext.odatabcn import validators
from collections import OrderedDict
from pylons import config
from routes.mapper import SubMapper

log = logging.getLogger(__name__)

## Custom authorization functions
def sysadmin_only(context, data_dict=None):
	if context.get('user'):
		return {'success': authz.is_sysadmin(context.get('user')),
				'msg': 'Only sysadmin are allowed to access this resource'}
	else:
		return {'success': False,
				'msg': 'Only users are allowed to access user profiles'}

@plugins.toolkit.auth_allow_anonymous_access
def logged_in_users_only(context, data_dict=None):

	if context.get('user'):
		return {'success': True}
	else:
		return {'success': False,
				'msg': 'Only users are allowed to access user profiles'}
				
@plugins.toolkit.auth_allow_anonymous_access
def logged_in_internal_use(context, data_dict=None):

	for_view = 'for_view' in context
	using_api = 'api_version' in context
	
	if context.get('user') or (not for_view and not using_api):
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
		map.connect(
			'tags_csv', '/tags.csv',
			controller='ckanext.odatabcn.controllers:CSVController',
			action='view_tags'
		)
		map.connect(
			'tags_html', '/tags',
			controller='ckanext.odatabcn.controllers:CSVController',
			action='view_tags_html'
		)
		map.connect(
			'/dataset/{id}/resource/{resource_id}/download',
			controller='ckanext.odatabcn.controllers:ResourceDownloadController',
			action='resource_download'
		)
		map.connect(
			'/dataset/{id}/resource/{resource_id}/download/{filename}',
			controller='ckanext.odatabcn.controllers:ResourceDownloadController',
			action='resource_download'
		)
		
		# Override API controller in order to track access
		GET = dict(method=['GET'])
		PUT = dict(method=['PUT'])
		POST = dict(method=['POST'])
		DELETE = dict(method=['DELETE'])
		GET_POST = dict(method=['GET', 'POST'])
		
		register_list = [
			'package',
			'dataset',
			'resource',
			'tag',
			'group',
			'revision',
			'licenses',
			'rating',
			'user',
			'activity'
		]
		register_list_str = '|'.join(register_list)
		
		with SubMapper(map, controller='ckanext.odatabcn.controllers:StatsApiController', path_prefix='/api{ver:/3|}',
				ver='/3') as m:
			m.connect('/action/{logic_function}', action='action',
				conditions=GET_POST)

		# /api ver 1, 2, 3 or none
		with SubMapper(map, controller='ckanext.odatabcn.controllers:StatsApiController', path_prefix='/api{ver:/1|/2|/3|}',
				ver='/1') as m:
			m.connect('', action='get_api')
			m.connect('/search/{register}', action='search')

		# /api ver 1, 2 or none
		with SubMapper(map, controller='ckanext.odatabcn.controllers:StatsApiController', path_prefix='/api{ver:/1|/2|}',
				ver='/1') as m:
			m.connect('/tag_counts', action='tag_counts')
			m.connect('/rest', action='index')
			m.connect('/qos/throughput/', action='throughput', conditions=GET)

		# /api/rest ver 1, 2 or none
		with SubMapper(map, controller='ckanext.odatabcn.controllers:StatsApiController', path_prefix='/api{ver:/1|/2|}',
				ver='/1', requirements=dict(register=register_list_str)
			) as m:

			m.connect('/rest/{register}', action='list', conditions=GET)
			m.connect('/rest/{register}', action='create', conditions=POST)
			m.connect('/rest/{register}/{id}', action='show', conditions=GET)
			m.connect('/rest/{register}/{id}', action='update', conditions=PUT)
			m.connect('/rest/{register}/{id}', action='update', conditions=POST)
			m.connect('/rest/{register}/{id}', action='delete', conditions=DELETE)
			m.connect('/rest/{register}/{id}/:subregister', action='list',
				conditions=GET)
			m.connect('/rest/{register}/{id}/:subregister', action='create',
				conditions=POST)
			m.connect('/rest/{register}/{id}/:subregister/{id2}', action='create',
				conditions=POST)
			m.connect('/rest/{register}/{id}/:subregister/{id2}', action='show',
				conditions=GET)
			m.connect('/rest/{register}/{id}/:subregister/{id2}', action='update',
				conditions=PUT)
			m.connect('/rest/{register}/{id}/:subregister/{id2}', action='delete',
				conditions=DELETE)

		# /api/util ver 1, 2 or none
		with SubMapper(map, controller='ckanext.odatabcn.controllers:StatsApiController', path_prefix='/api{ver:/1|/2|}',
				ver='/1') as m:
			m.connect('/util/user/autocomplete', action='user_autocomplete')
			m.connect('/util/is_slug_valid', action='is_slug_valid',
				conditions=GET)
			m.connect('/util/dataset/autocomplete', action='dataset_autocomplete',
				conditions=GET)
			m.connect('/util/tag/autocomplete', action='tag_autocomplete',
				conditions=GET)
			m.connect('/util/resource/format_autocomplete',
				action='format_autocomplete', conditions=GET)
			m.connect('/util/resource/format_icon',
				action='format_icon', conditions=GET)
			m.connect('/util/group/autocomplete', action='group_autocomplete')
			m.connect('/util/organization/autocomplete', action='organization_autocomplete',
				conditions=GET)
			m.connect('/util/markdown', action='markdown')
			m.connect('/util/dataset/munge_name', action='munge_package_name')
			m.connect('/util/dataset/munge_title_to_name',
				action='munge_title_to_package_name')
			m.connect('/util/tag/munge', action='munge_tag')
			m.connect('/util/status', action='status')
			m.connect('/util/snippet/{snippet_path:.*}', action='snippet')
			m.connect('/i18n/{lang}', action='i18n_js_translations')

		
		return map

	# Add custom facets
	def dataset_facets(self, facets_dict, package_type):
		facets_dict['geolocation'] = toolkit._('Geolocation')
		facets_dict['frequency'] = toolkit._('Frequency')
		#if toolkit.c.userobj:
		#	facets_dict['private'] = toolkit._('Private')
		return facets_dict
		
	def organization_facets(self, facets_dict, organization_type, package_type):
		facets_dict['geolocation'] = toolkit._('Geolocation')	
		facets_dict['frequency'] = toolkit._('Frequency')
		return facets_dict

	# Add created datasets to Drupal table to enable comments
	def notify(self, entity, operation=None):
	
		if operation == model.domain_object.DomainObjectOperation.new and isinstance(entity, (_package.Package)):
			
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
				
			log.debug("Inserting package %s: %s %s %s: %s %s %s %s" % (entity.id, entity.name, title_en, title_es, title_ca, desc_en, desc_es, desc_ca))
			
			try:
				drupal_cursor.execute("""insert into opendata_package (pkg_id,pkg_name,pkg_title_en,pkg_title_es,pkg_title_ca,pkg_description_en,pkg_description_es,pkg_description_ca) values (%s, %s, %s, %s, %s, %s, %s, %s)""", (entity.id, self.format_drupal_string(entity.name), self.format_drupal_string(title_en), self.format_drupal_string(title_es), self.format_drupal_string(title_ca), self.format_drupal_string(desc_en), self.format_drupal_string(desc_es), self.format_drupal_string(desc_ca)))
				drupal_conn.commit()
			except psycopg2.DataError, e:
				log.warn('Postgresql Database Exception %s', e.message)

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
		
		try:
			# Add download info and change resource url only if not downloading a resource, editing or indexing
			if not toolkit.c.action == 'resource_download':
				reload(sys)
				sys.setdefaultencoding('utf-8')
				dbc = parse_db_config('sqlalchemy.url')
				ckan_conn_string = "host='%s' dbname='%s' user='%s' password='%s'" % (dbc['db_host'], dbc['db_name'], dbc['db_user'], dbc['db_pass'])
				ckan_conn = psycopg2.connect(ckan_conn_string)
				ckan_cursor = ckan_conn.cursor()
				ckan_cursor.execute("""select sum(count), sum(count_absolute) from tracking_summary t inner join resource r on t.resource_id=r.id where tracking_type='resource' AND r.id=%s AND count IS NOT NULL AND count_absolute IS NOT NULL""", (resource_dict['id'],))
				row = ckan_cursor.fetchone()

				if len(row) != 0:
					resource_dict['downloads'] = row[0]
					resource_dict['downloads_absolute'] = row[1]
				else:
					resource_dict['downloads'] = '0'
					resource_dict['downloads_absolute'] = '0'

				ckan_cursor.close()
				ckan_conn.close()
				
				if (not toolkit.c.action == 'resource_edit' 
					and not toolkit.c.action == 'resource_delete'
					and not toolkit.c.action == 'new_resource'
					and not toolkit.c.action == 'edit'
					and not toolkit.c.action == ''):
					# Change resource download URLs in order to track downloads
					# Show original URLs for sysadmin when accessing through API
					if not resource_dict.get('url_type') == 'upload' and not (toolkit.c.user and authz.is_sysadmin(toolkit.c.user) and toolkit.c.controller == 'api'):
						site_url = config.get('ckan.site_url') + config.get('ckan.root_path').replace('{{LANG}}', '')
						resource_dict['url'] = '{site_url}dataset/{id}/resource/{resource_id}/download'.format(site_url=site_url, id=resource_dict['package_id'], resource_id=resource_dict['id']).encode('utf-8')
		except:
			log.error('An error occurred on the before_show method')
		

	# Add resource downloads to resource_search
	def after_search(context, search_results):

		try:
			if not (toolkit.c.user and authz.is_sysadmin(toolkit.c.user) and toolkit.c.controller == 'api'):
				site_url = config.get('ckan.site_url') + config.get('ckan.root_path').replace('{{LANG}}', '')
				for resource in search_results['results']:
					resource['url'] = '{site_url}dataset/{id}/resource/{resource_id}/download'.format(site_url=site_url, id=resource['package_id'], resource_id=resource['id']).encode('utf-8')
		except:
			log.error('An error occurred on the after_search method')
			
		return search_results
		
	
	# Override CKAN authorization functions
	def get_auth_functions(self):
		auth_functions = {
				'package_activity_list': update_auth.package_update,
				'package_delete': sysadmin_only,
				'user_show': logged_in_internal_use,
				'user_list': logged_in_users_only,
				'revision_list': logged_in_users_only,
				'group_revision_list': logged_in_users_only
			}
		
		return auth_functions
	

	# Custom validators
	def get_validators(self):
		return {
			'required_if_public': validators.required_if_public,
		}
	