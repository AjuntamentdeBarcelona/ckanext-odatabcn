import logging

import ast
import ckan.authz as authz
import ckan.logic as logic
import ckan.model as model
import ckan.plugins as plugins
import ckan.plugins.toolkit as toolkit
import pprint

from pylons import config

log = logging.getLogger(__name__)

def delete_private_data(pkg_dict):
	keys = (
			'maintainer', 
			'maintainer_email', 
			'maintainer_tel', 
			'broadcasting_maintainer', 
			'broadcasting_maintainer_tel', 
			'broadcasting_maintainer_email', 
			'broadcasting_management', 
			'broadcasting_department',
			'withdraw_date',
			'withdraw_reason',
			'metadata_created'
		)
	for key in keys:
		if key in pkg_dict:
			del pkg_dict[key]
			
def change_resource_download_urls(pkg_dict, site_url):
	for resource in pkg_dict['resources']:
		resource['url'] = '{site_url}dataset/{id}/resource/{resource_id}/download'.format(site_url=site_url, id=resource['package_id'], resource_id=resource['id']).encode('utf-8')
	

class EditfieldsPlugin(plugins.SingletonPlugin, toolkit.DefaultDatasetForm):
	plugins.implements(plugins.IPackageController, inherit=True)

	def after_show(self, context, pkg_dict): 
	
		#Execute package_activity_list auth function
		if toolkit.c.action == "activity":
			logic.check_access('package_activity_list', context, pkg_dict)
		
		#Do not show private data if user is not logged in
		if 'user' in context and not context['user']:
			delete_private_data(pkg_dict)
			
		#Actualiza valor de API en package	
		pkg_dict['api'] = 'No'	
		pkg_dict['token_required'] = 'No'	
		for resource in pkg_dict['resources']:
			if (resource['datastore_active']):
				pkg_dict['api'] = 'Yes'
				
			if ('token_required' in resource and resource['token_required'] == 'Yes'):
				pkg_dict['token_required'] = 'Yes'
			
	def before_search(self, search_params): 

		#Change default search order
		if not 'sort' in search_params:
			search_params['sort'] = 'fecha_publicacion desc'
		
		return search_params
			
	def after_search(self, search_results, search_params):
	
		# We need to add organization extras, since we need the translated
		# title and its parent organization
		if len(search_results['results']):
			context = {'model': model, 'session': model.Session,
						'user': toolkit.c.user, 'for_view': True,
						'auth_user_obj': toolkit.c.userobj}

			organization_list = toolkit.get_action('organization_list')(context, {
					'all_fields': True, 
					'include_dataset_count': False,
					'include_extras': True,
					'include_groups': True
				})
			
			organizations = {}
			for org in organization_list:
				organizations[org['name']] = org
				
			# Set the parent organization
			for key, value in organizations.iteritems():
				if len(value['groups']):
					for group in value['groups'][:1]:
						organizations[key]['parent'] = organizations[group['name']]
		
			for pkg in search_results['results']:
				pkg['organization'] = organizations[pkg['organization']['name']]
			
			# Assign the organization dict to org. facets
			if len(search_results['search_facets']) and 'organization' in search_results['search_facets']:
				for item in search_results['search_facets']['organization']['items']:
					item['organization'] = organizations[item['name']]
					
		#Do not include private data if user is not logged in
		#Change resource download URL to track downloads
		site_url = config.get('ckan.site_url') + config.get('ckan.root_path').replace('{{LANG}}', '')

		for pkg in search_results['results']:
		
			pkg['token_required'] = 'No'	
			
			if not toolkit.c.user:
				delete_private_data(pkg)
				
			for resource in pkg['resources']:			
				if ('token_required' in resource and resource['token_required'] == 'Yes'):
					pkg['token_required'] = 'Yes'
			
			if (not toolkit.c.action == 'resource_download'
					and not toolkit.c.action == 'resource_edit'
					and not toolkit.c.action == 'resource_delete'
					and not toolkit.c.action == 'resource_data'
					and not toolkit.c.action == 'new_resource'
					and not toolkit.c.action == 'edit'
					and not toolkit.c.action == ''
					and not (toolkit.c.user and authz.is_sysadmin(toolkit.c.user) and toolkit.c.controller == 'ckanext.odatabcn.controllers:StatsApiController')):
				change_resource_download_urls(pkg, site_url)

		return search_results

	def before_index(self, pkg_dict):
		delete_private_data(pkg_dict)
		return pkg_dict