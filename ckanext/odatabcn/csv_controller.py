import ckan.lib.i18n as i18n
import ckan.model as model
import ckan.plugins.toolkit as t
import datetime as d
import ast
import psycopg2
from ckan.model import Session
from ckan.common import _, OrderedDict, request, response
from ckan.lib.cli import parse_db_config
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
        year_from = 1989
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
                'fq': 'organization:(' + org_facets + ')',
                'include_private': True,
                'rows': 1000,
                'sort': 'name asc'
            })
            packages = packages['results']

        # obtenemos los formatos
        formats = t.get_action('format_autocomplete')(context, {
            'q': '',
            'limit': 50
        })
        # puede devolver formatos duplicados, lo convertimos a un set que eliminara los elementos
        # duplicados y de nuevo a una lista
        formats = list(set(formats))

        for format in formats:
            format_strip = format.strip()
            if not format_strip:
                formats.remove(format)

        # Realizamos conexion a la BBDD de Drupal para obtener el numero de comentarios de cada dataset y almacenamos los valores en un array
        dbc = parse_db_config('ckan.drupal.url')
        ckan_conn_string = "host='%s' port='%s' dbname='%s' user='%s' password='%s'" % (
        dbc['db_host'], dbc['db_port'], dbc['db_name'], dbc['db_user'], dbc['db_pass'])
        ckan_conn = psycopg2.connect(ckan_conn_string)
        ckan_cursor = ckan_conn.cursor()
        ckan_cursor.execute("""SELECT OP.pkg_name, COUNT(*) FROM opendata_package OP INNER JOIN node N ON N.tnid = OP.pkg_node_id INNER JOIN comment C ON C.nid = N.nid WHERE N.tnid != 0 GROUP BY OP.pkg_name;""")
        
        comments = {}

        for row in ckan_cursor:
            comments.update({row[0] : row[1]})
        ckan_cursor.close()
        ckan_conn.close()

        sql_downloads = '''select sum(count) AS downloads, sum(count_absolute) AS downloads_absolute, t.tracking_type, p.name from tracking_summary t
                                inner join resource r ON r.id = t.resource_id
                                inner join package p ON p.id = r.package_id
                                GROUP BY p.name, t.tracking_type;'''
        results_downloads = model.Session.execute(sql_downloads)

                                
        downloads = {}
        downloads_absolute = {}
        api_access_number = {}
        api_access_number_absolute = {}

        for row in results_downloads:
            if row.tracking_type == 'resource':
                downloads.update({row.name : row.downloads})
                downloads_absolute.update({row.name : row.downloads_absolute})
            else:
                api_access_number.update({row.name : row.downloads})
                api_access_number_absolute.update({row.name : row.downloads_absolute})

        sql_views = '''SELECT t.tracking_date, t.running_total, t.recent_views, t.package_id
                            FROM tracking_summary t
                            INNER JOIN
                                (SELECT package_id, MAX(tracking_date) AS tracking_date
                                FROM tracking_summary 
                                GROUP BY package_id) t2
                                ON t.package_id = t2.package_id
                            INNER JOIN package p ON p.id = t.package_id
                            AND t.tracking_date = t2.tracking_date;'''
        results_views = model.Session.execute(sql_views)

        tracking_total = {}
        tracking_recent = {}

        for row in results_views:
            tracking_total.update({row.package_id : row.running_total})
            tracking_recent.update({row.package_id : row.recent_views})

        # Incluimos la informacion que necesitamos mostrar para cada dataset
        for package in packages:
            for key in package['notes_translated']:
                if package['notes_translated'][key]:
                    package['notes_translated'][key] = package['notes_translated'][key].replace('\n', ' ').replace('\r',
                                                                                                                   ' ')

            # Obtenemos un string con las etiquetas
            tags = ''
            for tag in package['tags']:
                tags = tags + ' ' + tag['display_name']
            package['flattened_tags'] = tags

            # Obtenemos un string con los formatos de sus recursos, el total de descargas y el valor de openness_score del dataset
            # y si el dataset esta automatizado
            flattened_formats = ','
            qa = 0
            automatic = 'N'
            
            if 'update_string' in package and package['update_string']:
                automatic = 'S'

            for resource in package['resources']:
                if resource['format'].lower() not in flattened_formats:
                    # Lo rodeamos con otros caracteres para que los strings contenidos en otros no den resultado "true" (ej: XLS y XLSX)
                    flattened_formats = flattened_formats + resource['format'].lower() + ','

                if automatic == 'N':
                    if (
                            not resource['url_type'] == 'upload' and
                            not '/resources/opendata/' in resource['url'] and
                            not '/resource/' + resource['id'] + '/download/' in resource['url']
                    ):
                        automatic = 'S'

                if 'qa' in resource:
                    resource_qa = ast.literal_eval(resource['qa'])
                    if (resource_qa['openness_score'] > qa):
                        qa = int(resource_qa['openness_score'])
                        

            package['flattened_formats'] = flattened_formats
            package['automatic'] = automatic
            package['qa'] = qa

            # Establecemos la tabla de formatos para cada dataset
            package['formats'] = OrderedDict()

            for format in formats:
                format_value = 'N'
                if ',' + format + ',' in flattened_formats:
                    format_value = 'S'

                package['formats'][format] = format_value

            # Establecemos la tabla de anyos para cada dataset
            package['years'] = OrderedDict()
            for year in range(year_from, year_to + 1):
                year_value = 'N'
                if 'Any ' + str(year) in package['flattened_tags']:
                    year_value = 'S'

                package['years'][year] = year_value

            # Escapamos los campos de texto
            self.escape_text(package)
            self.escape_translated_text(package)

            # Obtenemos numero comentarios
            if (package['name'] in comments):
                package['comments'] = comments[package['name']]
            else:
                package['comments'] = 0
            
            if (package['name'] in downloads):
                package['downloads'] = downloads[package['name']]
            else:
                package['downloads'] = 0
            
            if (package['name'] in downloads_absolute):
                package['downloads_absolute'] = downloads_absolute[package['name']]
            else:
                package['downloads_absolute'] = 0
            
            if (package['name'] in api_access_number):
                package['api_access_number'] = api_access_number[package['name']]
            else:
                package['api_access_number'] = 0
            
            if (package['name'] in api_access_number_absolute):
                package['api_access_number_absolute'] = api_access_number_absolute[package['name']]
            else:
                package['api_access_number_absolute'] = 0

            if (package['id'] in tracking_total):
                package['tracking_total'] = tracking_total[package['id']]
            else:
                package['tracking_total'] = 0

            if (package['id'] in tracking_recent):
                package['tracking_recent'] = tracking_recent[package['id']]
            else:
                package['tracking_recent'] = 0

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

    def view_tags(self):

        # Obtenemos los tags
        sql = '''SELECT T.name as name_tag, COUNT(*) as total_tag FROM tag T
                    INNER JOIN package_tag PT ON PT.tag_id = T.id
                    INNER JOIN package P ON P.id = PT.package_id
                    WHERE PT.state LIKE 'active' AND PT.package_id IS NOT NULL AND PT.package_id NOT LIKE '' AND P.private = FALSE
                    GROUP BY T.name
                    ORDER BY T.name;'''
        results = model.Session.execute(sql)

        curdate = d.datetime.now().strftime('%Y-%m-%d_%H-%M')
        t.response.headers['Content-Type'] = 'application/csv; charset=utf-8'
        t.response.headers['Content-Disposition'] = 'attachment; filename=tagsBCN_' + curdate + '.csv'
        return t.render('tags.csv', extra_vars={
            'tags': results
        })