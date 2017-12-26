import logging

import ast
import ckan.logic as logic
import ckan.model as model
import ckan.plugins as plugins
import ckan.plugins.toolkit as toolkit

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

class EditfieldsPlugin(plugins.SingletonPlugin, toolkit.DefaultDatasetForm):
	plugins.implements(plugins.IPackageController, inherit=True)

	def after_show(self, context, pkg_dict): 
	
		#Execute package_activity_list auth function
		if toolkit.c.action == "activity":
			logic.check_access('package_activity_list', context, pkg_dict)
		
		#Do not show private data if user is not logged in
		if 'user' in context and not context['user']:
			delete_private_data(pkg_dict)
			
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
		if not toolkit.c.user:
			for pkg in search_results['results']:
				delete_private_data(pkg)
			
			for pkg in search_results:
				delete_private_data(pkg)

		return search_results

	def before_index(self, pkg_dict):
		delete_private_data(pkg_dict)
		return pkg_dict