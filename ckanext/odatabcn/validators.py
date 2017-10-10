import logging
import json

from ckan.plugins.toolkit import _
	
log = logging.getLogger(__name__)
	
# Require field if dataset visibility is public
def required_if_public(key, data, errors, context):
	value = data[key]
	private = data[('private',)]
	
	if private == 'False' and not value:
		errors[key].append(_('This field is required'))

