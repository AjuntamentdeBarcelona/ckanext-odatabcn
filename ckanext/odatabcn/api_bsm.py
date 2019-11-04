 #!/usr/bin/env python
# -*- coding: utf-8 -*-

from datetime import datetime
import ast
import csv
import urllib2
import urllib
import json
import os
import requests
from oauthlib.oauth2 import BackendApplicationClient
import pprint
import requests_oauthlib
import sys
import time
import os, ssl
from ckanext.odatabcn.api import CustomApi
from pylons import config
#from api import CustomApi
if (not os.environ.get('PYTHONHTTPSVERIFY', '') and getattr(ssl, '_create_unverified_context', None)): 
    ssl._create_default_https_context = ssl._create_unverified_context
    
log = __import__('logging').getLogger(__name__)

'''
Obtain a dataset from the BSM API manager
'''

class BsmApi (CustomApi):

    PROVIDER_NAME = 'bsm'

    resource = None
    app_token = None
    user_token = None
    user_id = None
    user_key = None
    user_secret = None
    user_token = None
    username = None
    email = None

    def __init__(self, resource, app_token, consumer_key, consumer_secret, user_token, user_id, user_key, user_secret, username, email):
    
        super(BsmApi, self).__init__()
    
        self.resource = resource
        self.app_token = app_token
        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret
        self.user_token = user_token
        self.user_id = user_id
        self.user_key = user_key
        self.user_secret = user_secret
        self.username = username
        self.email = email
        
        if app_token:
            self.app_token = ast.literal_eval(app_token)
        
        if user_token:
            self.user_token = ast.literal_eval(user_token)
            
        
    def execute(self):
        if (not self.user_key): 
            #Register user
            self.user_token = self.registerUser()

        return self.getResource()
   
            
    def registerUser(self):
        pprint.pprint("registerUser")
        pprint.pprint(self.username)
        url_signup = config.get('ckanext.odatabcn.api.bsm.url.signup')
        
        self.username = super(BsmApi, self).getUsername(self.username)
        password = super(BsmApi, self).randomString()
        api_name, api_version, api_provider = self.getApiInfo()
        data = {
                'user': {
                    'username': self.username,
                    'email': self.email,
                    'password': password 
                    },
                'api': {
                    'apiName': api_name,
                    'apiVersion': api_version,
                    'apiProvider': api_provider
                    }
            }

        response = self.sendData(url_signup, data, 'POST')

        if response.status_code == 201 or response.status_code == 200:
            json_response = response.json()
            self.user_key = json_response['consumerKey']
            self.user_secret = json_response['consumerSecret']
            super(BsmApi, self).saveUser(self.user_id, self.PROVIDER_NAME, self.user_key, self.user_secret)
            return json_response['token']['accessToken']
            
    def subscribeUser(self):
        url_subscription = config.get('ckanext.odatabcn.api.bsm.url.subscription').replace('{username}', self.username)
        
        api_name, api_version, api_provider = self.getApiInfo()
        data = {
                'api': {
                    'apiName': api_name,
                    'apiVersion': api_version,
                    'apiProvider': api_provider
                    }
            }
        
        response = self.sendData(url_subscription, data, 'PUT')

        return response.status_code
        
        
    def sendData(self, url, data, method='POST'):

        session = self.getAppSession()

        headers = {'Content-type': 'application/json'}
        
        if (method == 'POST'):
            response = session.post(url, data=json.dumps(data), headers=headers, verify=False)
        else:
            response = session.put(url, data=json.dumps(data), headers=headers, verify=False)

        return response
        
        
    def getAppSession(self):
        if not self.app_token or ('expires_at' in self.app_token and time.time() > self.app_token['expires_at']):
            client = BackendApplicationClient(client_id=self.consumer_key)
            session = requests_oauthlib.OAuth2Session(client=client)
        
            self.app_token = session.fetch_token(
                token_url=config.get('ckanext.odatabcn.api.bsm.url.token'),
                client_id=self.consumer_key,
                client_secret=self.consumer_secret,
                verify=False
            )
            
            super(BsmApi, self).saveAppToken(self.app_token, self.PROVIDER_NAME)
            
        else:
            session = requests_oauthlib.OAuth2Session(token = {'access_token': self.app_token['access_token']})
        
        return session
        
    def getUserSession(self):
        if not self.user_token or ('expires_at' in self.user_token and time.time() > self.user_token['expires_at']):
            client_user = BackendApplicationClient(client_id=self.user_key)
            session = requests_oauthlib.OAuth2Session(client=client_user)

            self.user_token = session.fetch_token(
                token_url=config.get('ckanext.odatabcn.api.bsm.url.token'),
                client_id=self.user_key,
                client_secret=self.user_secret,
                verify=False
            )
            
            super(BsmApi, self).saveUserToken(self.user_token, self.user_id, self.PROVIDER_NAME)
        else:
            session = requests_oauthlib.OAuth2Session(token = {'access_token': self.user_token['access_token']})
        
        return session
        
            
    def getResource(self):
        user_session = self.getUserSession()

        resource_response = user_session.get(self.resource['url'], verify=False)

        if not resource_response.status_code == 403:
            return resource_response.content, resource_response.status_code, resource_response.headers
        elif self.subscribeUser() == 200:
                self.getResource()
            
    def getApiInfo(self):
        url_parts = self.resource['url'].split('/')
        api_name = url_parts[-3]
        api_version = url_parts[-2]
        return api_name, api_version, self.resource['token_provider']