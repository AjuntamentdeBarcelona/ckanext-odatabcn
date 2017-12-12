import ckan.lib.app_globals as app_globals
import ckan.lib.i18n as i18n
import ckan.model as model
import ckan.plugins.toolkit as t
import datetime as d
import mimetypes as m
from ckan.lib.render import TemplateNotFound
from ckan.common import OrderedDict, request
from pylons import config

log = __import__('logging').getLogger(__name__)
namespace = 'ckanext.odatabcn'

c = t.c


class CSVController(t.BaseController):

	def view(self):
		
		context = {'model': model, 'session': model.Session,
					'user': c.user, 'for_view': True,
					'auth_user_obj': c.userobj}
		
		# Obtenemos parametros de configuracion
		site_url = config.get('ckan.site_url') + config.get('ckan.root_path').replace('{{LANG}}', '')
		
		# Inicializamos variables
		now = d.datetime.now()
		year_from = 2005
		year_to = now.year
		
		# Comprobamos si es un usuario identificado o no
		logged_in = False
		if 'user' in context and context['user']:
			logged_in = True
			
		# Si se pide el catalogo publico ignoramos el usuario identificado
		if logged_in and 'public' in request.params and request.params.get('public') == 'true':
			logged_in = False

		if not logged_in:
			# Obtenemos el catalogo para usuarios no identificados
			packages = t.get_action('package_search')(context, {
					'include_private': False,
					'rows': 1000,
					'sort': 'name asc'
				})
			packages = packages['results']
		elif c.userobj.sysadmin:
			# Obtenemos el catalogo para sysadmin
			packages = t.get_action('package_search')(context, {
					'include_private': True,
					'rows': 1000,
					'sort': 'name asc'
				})
			packages = packages['results']
		else:
			# Obtenemos el catalogo para usuarios identificados: solo los de sus organizaciones
			user_org = t.get_action('organization_list_for_user')(context, {
					'permission': 'create_dataset'
				})
			org_facets = ''
			for org in user_org:
				if org_facets != '':
					org_facets = org_facets + ' OR '
				org_facets = org_facets + org['name']
			
			packages = t.get_action('package_search')(context, {
					'fq': 'organization:('+ org_facets +')',
					'include_private': True,
					'rows': 1000,
					'sort': 'name asc'
				})
			packages = packages['results']
		
		# obtenemos los formatos
		formats = t.get_action('format_autocomplete')(context, {
				'q': '',
				'limit': 20
			})
		# puede devolver formatos duplicados, lo convertimos a un set que eliminara los elementos 
		# duplicados y de nuevo a una lista
		formats = list(set(formats))

		# Incluimos la informacion que necesitamos mostrar para cada dataset
		for package in packages:
			for key in package['notes_translated']:
				if package['notes_translated'][key]:
					package['notes_translated'][key] = package['notes_translated'][key].replace('\n', ' ').replace('\r', ' ')
			
			#Obtenemos las vistas y descargas
			sql = '''SELECT SUM(count) AS total, package_id 
						FROM tracking_summary 
						WHERE package_id LIKE '%s' GROUP BY package_id;''' % (package['id'])
			results = model.Session.execute(sql)
		
			for m in results:
				package['tracking_total'] = str(m.total)
			
			#Obtenemos un string con las etiquetas
			tags = ''
			for tag in package['tags']:
				tags = tags + ' ' + tag['display_name']
			package['flattened_tags'] = tags 

			
			# Obtenemos un string con los formatos de sus recursos, el total de descargas 
			# y si el dataset esta automatizado
			flattened_formats = ','
			downloads = 0
			downloads_absolute = 0
			automatic = 'N'
			if 'update_string' in package and package['update_string']:
				automatic = 'S'
			
			for resource in package['resources']:
				if resource['format'].lower() not in flattened_formats:
					# Lo rodeamos con otros caracteres para que los strings contenidos en otros no den resultado "true" (ej: XLS y XLSX)
					flattened_formats = flattened_formats + resource['format'].lower() + ','
					
				if not (resource['downloads'] == 'None'):
					downloads += int(resource['downloads'])
					
				if 'downloads_absolute' in resource and not (resource['downloads_absolute'] == 'None'):
					downloads_absolute += int(resource['downloads_absolute'])
				
				if automatic == 'N':
					if (
						not resource['url_type'] == 'upload' and
						not '/resources/opendata/' in resource['url'] and
						not '/resource/' + resource['id'] + '/download/' in resource['url']
						):
							automatic = 'S'
					
					
			package['flattened_formats'] = flattened_formats
			package['downloads'] = downloads
			package['downloads_absolute'] = downloads_absolute
			package['automatic'] = automatic
			
			# Establecemos la tabla de formatos para cada dataset
			package['formats'] = OrderedDict()
			for format in formats:
				format_value = 'N'
				if ',' + format + ',' in flattened_formats:
					format_value = 'S'
				
				package['formats'][format] = format_value
					
			# Establecemos la tabla de anyos para cada dataset
			package['years'] = OrderedDict()
			for year in range (year_from, year_to):
				year_value = 'N'
				if 'Any ' + str(year) in package['flattened_tags']:
					year_value = 'S'
				
				package['years'][year] = year_value
				
			# Escapamos los campos de texto
			self.escape_text(package)
			self.escape_translated_text(package)
				
		
		curdate = d.datetime.now().strftime('%Y-%m-%d_%H-%M')
		t.response.headers['Content-Type'] = 'application/csv; charset=utf-8'
		t.response.headers['Content-Disposition'] = 'attachment; filename=catalegBCN_' + curdate + '.csv'
		return t.render('cataleg.csv', extra_vars={
				'site_url': site_url,
				'packages': packages,
				'logged_in': logged_in,
				'formats': formats,
				'year_from': year_from,
				'year_to': year_to,
				'user': c.user, 
				'auth_user_obj': c.userobj,
				'request': request
			})
			
	def escape_text(self, pkg_dict):
		keys = (
			'author',
			'department',
			'flattened_tags',
			'fuente',
			'license_title',
			'maintainer', 
			'maintainer_email', 
			'maintainer_tel', 
			'broadcasting_maintainer', 
			'broadcasting_maintainer_tel', 
			'broadcasting_maintainer_email', 
			'broadcasting_management', 
			'broadcasting_department',
			'observations'
		)
		
		for key in keys:
			if key in pkg_dict:
				pkg_dict[key] = pkg_dict[key].replace('"', '""')
			
	def escape_translated_text(self, pkg_dict):
		keys = (
			'title', 
			'notes' 
		)
		
		for key in keys:
			for locale in i18n.get_locales():
				if key + '_translated' in pkg_dict:
					pkg_dict[key + '_translated'][locale] = pkg_dict[key + '_translated'][locale].replace('"', '""')