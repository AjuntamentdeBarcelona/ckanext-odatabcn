#!/usr/bin/env python
# -*- coding: utf-8 -*-

import ckan.lib.base as base
import ckan.lib.helpers as h
import ckan.lib.uploader as uploader
import ckan.logic as logic
import ckan.model as model
import ckan.plugins.toolkit as t
import datetime as d
import hashlib
import ast
import mimetypes as m
import model as extmodel
import paste.fileapp
import psycopg2
import requests
import unicodedata
from ckan.common import _, OrderedDict, request, response
from ckan.controllers.api import ApiController
from ckan.lib.cli import parse_db_config
from pylons.controllers.util import redirect

log = __import__('logging').getLogger(__name__)
namespace = 'ckanext.odatabcn'

c = t.c


class TagsController(t.BaseController):

    def view_tags_html(self):

        # Obtenemos los tags
        sql = '''SELECT T.name as name_tag, COUNT(*) as total_tag FROM tag T
                    INNER JOIN package_tag PT ON PT.tag_id = T.id
                    INNER JOIN package P ON P.id = PT.package_id
                    WHERE PT.state LIKE 'active' AND PT.package_id IS NOT NULL AND PT.package_id NOT LIKE '' AND P.private = FALSE
                    GROUP BY T.name
                    ORDER BY T.name;'''
        results = model.Session.execute(sql)

        t.response.headers['Content-Type'] = 'text/html; charset=utf-8'
        return t.render('tags.html', extra_vars={
            'tags': results,
            'unicodedata': unicodedata
        })


class ResourceDownloadController(t.BaseController):

    def resource_download(self, environ, id, resource_id, filename=None):

        context = {'model': model, 'session': model.Session,
                   'user': c.user, 'auth_user_obj': c.userobj}

        try:
            rsc = t.get_action('resource_show')(context, {'id': resource_id})
        except (logic.NotFound, logic.NotAuthorized):
            base.abort(404, _('Resource not found'))

        headers = {
            'X-Forwarded-For': environ.get('REMOTE_ADDR'),
            'User-Agent': environ.get('HTTP_USER_AGENT'),
            'Accept-Language': environ.get('HTTP_ACCEPT_LANGUAGE', ''),
            'Accept-Encoding': environ.get('HTTP_ACCEPT_ENCODING', '')
        }

        if rsc.get('token_required') == 'Yes':
            authentication = environ.get('HTTP_AUTHORIZATION', '')

            if authentication == '':
                 return t.render('package/error_tokens.html')
            dbd = parse_db_config('ckan.drupal.url')
            drupal_conn_string = "host='%s' dbname='%s' port='%s' user='%s' password='%s'" % (dbd['db_host'], dbd['db_name'], dbd['db_port'], dbd['db_user'], dbd['db_pass'])
            drupal_conn = psycopg2.connect(drupal_conn_string)
            drupal_cursor = drupal_conn.cursor()
            drupal_cursor.execute("""select id_usuario from opendata_tokens where tkn_usuario=%s""", (authentication,))

            if drupal_cursor.rowcount < 1:
                base.abort(403, _('El token no existe y no se permite la descarga del recurso'))

        # Save download to tracking_raw
        CustomTrackingController.update(environ['REQUEST_URI'], 'resource', environ)
        
        if rsc.get('url_type') == 'upload':
            # Internal redirect
            upload = uploader.get_resource_uploader(rsc)
            filepath = upload.get_path(rsc['id'])
            fileapp = paste.fileapp.FileApp(filepath)

            try:
                status, headers, app_iter = request.call_application(fileapp)
            except OSError:
                base.abort(404, _('Resource data not found'))
            response.headers.update(dict(headers))
            content_type, content_enc = m.guess_type(rsc.get('url', ''))

            if content_type and content_type == 'application/xml':
                response.headers['Content-Type'] = 'application/octet-stream'
            elif content_type:
                response.headers['Content-Type'] = content_type

            response.status = status
            return app_iter

            h.redirect_to(rsc['url'].encode('utf-8'))
        elif 'url' not in rsc:
            base.abort(404, _('No download is available'))
        else:
            # External redirect
            return redirect(rsc['url'].encode('utf-8'))


class StatsApiController(ApiController):

    def __call__(self, environ, start_response):
        # Save access to tracking_raw
        CustomTrackingController.update(environ['REQUEST_URI'], 'api', environ)

        return ApiController.__call__(self, environ, start_response)

class CustomTrackingController:

    @staticmethod
    def update(url, type, environ):

        # we want a unique anonimized key for each user so that we do
        # not count multiple clicks from the same user.
        key = ''.join([
            environ.get('HTTP_USER_AGENT', ''),
            environ.get('REMOTE_ADDR', ''),
            environ.get('HTTP_ACCEPT_LANGUAGE', ''),
            environ.get('HTTP_ACCEPT_ENCODING', ''),
        ])
        key = hashlib.md5(key).hexdigest()
        tracking = extmodel.TrackingRaw(user_key = key, url = url, tracking_type = type)
        model.Session.add(tracking)
        model.Session.commit()