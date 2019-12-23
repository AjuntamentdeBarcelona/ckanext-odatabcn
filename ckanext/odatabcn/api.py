#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pprint
import psycopg2
import random
import re
import string
from ckan.lib.cli import parse_db_config

class CustomApi(object):

    def __init__(self):
        pass
        
    def randomString(self, stringLength=10):
        letters = string.ascii_letters
        return ''.join(random.choice(letters) for i in range(stringLength))

    def getUsername(self, username):
        pattern = re.compile('[\W_]+')
        username = pattern.sub('', username.lower())
        return 'opendatabcn_' + username
        
    def saveUser(self, user_id, provider, user_key, user_secret):
        pprint.pprint("save user")
        dbd = parse_db_config('ckan.drupal.url')
        drupal_conn_string = "host='%s' dbname='%s' port='%s' user='%s' password='%s'" % (dbd['db_host'], dbd['db_name'], dbd['db_port'], dbd['db_user'], dbd['db_pass'])
        drupal_conn = psycopg2.connect(drupal_conn_string)
        drupal_cursor = drupal_conn.cursor(cursor_factory = psycopg2.extras.DictCursor)
        drupal_cursor.execute("""INSERT INTO opendata_tokens_provider_user (id_usuario, provider, key, secret) VALUES (%s, %s, %s, %s)""", (user_id, provider, user_key, user_secret))
        drupal_conn.commit()
        
    def saveAppToken(self, app_token, provider):
        pprint.pprint("store app token")
        app_token = str(app_token)
        pprint.pprint(str(app_token))
        dbd = parse_db_config('ckan.drupal.url')
        drupal_conn_string = "host='%s' dbname='%s' port='%s' user='%s' password='%s'" % (dbd['db_host'], dbd['db_name'], dbd['db_port'], dbd['db_user'], dbd['db_pass'])
        drupal_conn = psycopg2.connect(drupal_conn_string)
        drupal_cursor = drupal_conn.cursor(cursor_factory = psycopg2.extras.DictCursor)
        drupal_cursor.execute("""UPDATE opendata_tokens_provider SET app_token=%s WHERE id=%s""", (app_token, provider))
        drupal_conn.commit()
    
    def saveUserToken(self, user_token, user_id, provider):
        pprint.pprint("store user token")
        pprint.pprint(str(user_token))
        dbd = parse_db_config('ckan.drupal.url')
        drupal_conn_string = "host='%s' dbname='%s' port='%s' user='%s' password='%s'" % (dbd['db_host'], dbd['db_name'], dbd['db_port'], dbd['db_user'], dbd['db_pass'])
        drupal_conn = psycopg2.connect(drupal_conn_string)
        drupal_cursor = drupal_conn.cursor(cursor_factory = psycopg2.extras.DictCursor)
        drupal_cursor.execute("""UPDATE opendata_tokens_provider_user SET token=%s WHERE id_usuario=%s AND provider=%s""", (str(user_token), user_id, provider))
        drupal_conn.commit()
        
    def genericError(self):
        error_content = {"error": "Error en la cridada a la API"}
        headers = {}
        headers['content-type'] = "application/json"
        return error_content, 500, headers